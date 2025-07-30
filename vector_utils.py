import boto3
import json
from qdrant_client import QdrantClient
import os
import hashlib
from qdrant_client.http.models import PointStruct

# Titan Embeddings
client = boto3.client("bedrock-runtime", region_name="us-east-1")
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"

# Qdrant
from qdrant import qdrant_client

COLLECTION_NAME = "sop_embeddings"


def embed_text(text):
    request = json.dumps({"inputText": text})
    response = client.invoke_model(modelId=TITAN_MODEL_ID, body=request)
    model_response = json.loads(response["body"].read())
    return model_response["embedding"]


def upsert_embedding(id, text, metadata=None):
    vector = embed_text(text)
    # Qdrant requires point IDs to be int or UUID, so hash the id string
    point_id = int(hashlib.sha256(id.encode()).hexdigest(), 16) % (10 ** 12)
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=vector, payload=metadata or {})]
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
    vector = embed_text(query)
    results = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=top_k
    )
    questions = []
    import re
    for hit in results:
        # hit.payload is a dict like {'source': ..., 'chunk': ...}
        # hit.vector is the embedding, hit.id is the point id
        # We need to get the original chunk text from the vector store
        # But since we only stored metadata, we need to re-read the chunk from file
        source = hit.payload.get('source')
        chunk_idx = hit.payload.get('chunk')
        if source and chunk_idx is not None:
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
        if len(questions) >= top_k:
            break
    return questions[:top_k] 