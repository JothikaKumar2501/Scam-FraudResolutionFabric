import boto3
import json
from qdrant_client import QdrantClient
import os
import hashlib
from functools import lru_cache
from qdrant_client.http.models import PointStruct

# Titan Embeddings (use env override)
TITAN_MODEL_ID = os.getenv("AWS_TITAN_MODEL_ID", "amazon.titan-embed-text-v2:0")

# Qdrant
from qdrant import qdrant_client, ensure_collection

COLLECTION_NAME = "sop_embeddings"
# VECTOR_SIZE is determined dynamically from the embedding length to avoid mismatches
DEFAULT_VECTOR_SIZE = 1024


_bedrock_client = None

def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _bedrock_client

@lru_cache(maxsize=2048)
def _fallback_embed(text: str, dim: int = DEFAULT_VECTOR_SIZE):
    # Deterministic fallback embedding using SHA256
    import math
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Expand hash to requested dimension deterministically
    values = []
    idx = 0
    while len(values) < dim:
        byte = h[idx % len(h)]
        values.append(((byte / 255.0) - 0.5) * 2.0)
        idx += 1
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]

@lru_cache(maxsize=1024)
def embed_text(text: str):
    request = json.dumps({"inputText": text})
    try:
        response = _get_bedrock_client().invoke_model(modelId=TITAN_MODEL_ID, body=request)
        model_response = json.loads(response["body"].read())
        embedding = model_response.get("embedding")
        if not embedding:
            # Some SDK variants use 'embeddings'
            embedding = model_response.get("embeddings", {}).get("values")
        if not embedding:
            return _fallback_embed(text)
        return embedding
    except Exception:
        # Graceful fallback when Bedrock isn't configured
        return _fallback_embed(text)


def upsert_embedding(id, text, metadata=None):
    # Compute embedding first to get vector size
    vector = embed_text(text)
    vector_size = len(vector) if isinstance(vector, list) else DEFAULT_VECTOR_SIZE
    # Ensure collection exists before upsert (idempotent)
    try:
        ensure_collection(COLLECTION_NAME, vector_size)
    except Exception:
        pass
    # Qdrant requires point IDs to be int or UUID, so hash the id string
    point_id = int(hashlib.sha256(id.encode()).hexdigest(), 16) % (10 ** 12)
    try:
        # Prefer newer upsert signature with points
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload=metadata or {})]
        )
    except Exception:
        # Fallback to older clients expecting list of dicts
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[{"id": point_id, "vector": vector, "payload": (metadata or {})}]
        )


def ingest_documents(doc_paths):
    """Ingest and embed documents (chunked if large) into Qdrant."""
    for path in doc_paths:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Simple chunking: split by paragraphs (or every 1000 chars)
        chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
        for i, chunk in enumerate(chunks):
            doc_id = f"{os.path.basename(path)}_{i}"
            upsert_embedding(doc_id, chunk, metadata={"source": path, "chunk": i})


def search_similar(query, top_k=3):
    # Compute embedding first to get vector size
    vector = embed_text(query)
    vector_size = len(vector) if isinstance(vector, list) else DEFAULT_VECTOR_SIZE
    # Lazy ensure collection before search
    try:
        ensure_collection(COLLECTION_NAME, vector_size)
    except Exception:
        pass
    # Prefer newer query_points API; fallback to search for older clients
    try:
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=top_k,
            with_payload=True
        )
        # query_points returns a SearchResult object, access the points attribute
        hits = results.points
    except Exception as e:
        # Fallback to search method for older clients
        try:
            hits = qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=top_k
            )
        except Exception as search_error:
            print(f"Error in both query_points and search: {e}, {search_error}")
            return []
    
    questions = []
    import re
    for hit in hits:
        # hit.payload is a dict like {'source': ..., 'chunk': ...}
        # hit.vector is the embedding, hit.id is the point id
        # We need to get the original chunk text from the vector store
        # But since we only stored metadata, we need to re-read the chunk from file
        source = hit.payload.get('source')
        chunk_idx = hit.payload.get('chunk')
        if source and chunk_idx is not None:
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    content = f.read()
                chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
                chunk = chunks[chunk_idx] if chunk_idx < len(chunks) else ''
                # Extract questions from the chunk
                # Look for lines that start with - or * and contain a ?
                for line in chunk.split('\n'):
                    line = line.strip()
                    if (line.startswith('-') or line.startswith('*')) and '?' in line:
                        # Remove leading - or * and whitespace/quotes
                        q = re.sub(r'^[-*\s\"]+', '', line)
                        questions.append(q)
            except (FileNotFoundError, IOError) as file_error:
                print(f"Error reading file {source}: {file_error}")
                continue
        if len(questions) >= top_k:
            break
    return questions[:top_k]

# --- Enhanced RAG Functions ---

def search_sop_rules(query, rule_id=None, top_k=5):
    """Enhanced SOP rule search with context awareness"""
    try:
        # Create enhanced search query
        enhanced_query = f"SOP rules {query}"
        if rule_id:
            enhanced_query += f" rule_id {rule_id}"
        
        vector = embed_text(enhanced_query)
        vector_size = len(vector) if isinstance(vector, list) else DEFAULT_VECTOR_SIZE
        try:
            ensure_collection(COLLECTION_NAME, vector_size)
        except Exception:
            pass
        
        # Search in Qdrant
        try:
            results = qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=vector,
                limit=top_k,
                with_payload=True
            )
            hits = results.points
        except Exception as e:
            hits = qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=top_k
            )
        
        # Extract SOP rules from hits
        sop_rules = []
        for hit in hits:
            source = hit.payload.get('source')
            chunk_idx = hit.payload.get('chunk')
            if source and 'SOP.md' in source and chunk_idx is not None:
                try:
                    with open(source, 'r', encoding='utf-8') as f:
                        content = f.read()
                    chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
                    chunk = chunks[chunk_idx] if chunk_idx < len(chunks) else ''
                    
                    # Extract SOP rules (table rows or rule definitions)
                    import re
                    # Look for table rows with rule information
                    table_rows = re.findall(r'\|[^\n]*\|', chunk)
                    for row in table_rows:
                        if rule_id and rule_id in row:
                            sop_rules.append(row.strip())
                    
                    # Look for rule definitions
                    rule_patterns = re.findall(r'Rule ID[^\n]*', chunk, re.IGNORECASE)
                    sop_rules.extend(rule_patterns)
                    
                except (FileNotFoundError, IOError) as file_error:
                    print(f"Error reading SOP file {source}: {file_error}")
                    continue
        
        return sop_rules[:top_k]
        
    except Exception as e:
        print(f"Error in SOP rule search: {e}")
        return []

def search_contextual_questions(query, rule_id=None, context=None, top_k=5):
    """Enhanced question search with context awareness"""
    try:
        # Create enhanced search query
        enhanced_query = f"questions {query}"
        if rule_id:
            enhanced_query += f" rule_id {rule_id}"
        if context:
            enhanced_query += f" context {context}"
        
        vector = embed_text(enhanced_query)
        vector_size = len(vector) if isinstance(vector, list) else DEFAULT_VECTOR_SIZE
        try:
            ensure_collection(COLLECTION_NAME, vector_size)
        except Exception:
            pass
        
        # Search in Qdrant
        try:
            results = qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                query=vector,
                limit=top_k
            )
            hits = results.points
        except Exception as e:
            hits = qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=top_k
            )
        
        # Extract questions from hits
        questions = []
        for hit in hits:
            source = hit.payload.get('source')
            chunk_idx = hit.payload.get('chunk')
            if source and 'questions.md' in source and chunk_idx is not None:
                try:
                    with open(source, 'r', encoding='utf-8') as f:
                        content = f.read()
                    chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
                    chunk = chunks[chunk_idx] if chunk_idx < len(chunks) else ''
                    
                    # Extract questions
                    import re
                    # Look for quoted questions
                    quoted_questions = re.findall(r'"([^"]*\?)"', chunk)
                    questions.extend(quoted_questions)
                    
                    # Look for bullet point questions
                    bullet_questions = re.findall(r'^\*\s+"([^"]+)"', chunk, re.MULTILINE)
                    questions.extend(bullet_questions)
                    
                except (FileNotFoundError, IOError) as file_error:
                    print(f"Error reading questions file {source}: {file_error}")
                    continue
        
        return questions[:top_k]
        
    except Exception as e:
        print(f"Error in contextual question search: {e}")
        return []

def get_relevant_context(query, context_type="mixed", top_k=3):
    """Get relevant context from multiple sources"""
    try:
        # Search for SOP rules
        sop_rules = search_sop_rules(query, top_k=top_k//2)
        
        # Search for questions
        questions = search_contextual_questions(query, top_k=top_k//2)
        
        # Combine results based on context type
        if context_type == "sop":
            return {"sop_rules": sop_rules, "questions": []}
        elif context_type == "questions":
            return {"sop_rules": [], "questions": questions}
        else:
            return {"sop_rules": sop_rules, "questions": questions}
            
    except Exception as e:
        print(f"Error getting relevant context: {e}")
        return {"sop_rules": [], "questions": []} 