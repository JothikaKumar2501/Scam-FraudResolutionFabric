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
    return [hit.payload for hit in results] 