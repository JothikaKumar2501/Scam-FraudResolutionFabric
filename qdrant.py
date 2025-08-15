import os
import math
from typing import List, Dict, Any
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    QDRANT_SDK_AVAILABLE = True
except Exception:
    QDRANT_SDK_AVAILABLE = False

"""
Qdrant client wrapper with in-memory stub fallback.
If QDRANT_URL is not provided, or QDRANT_STUB=1, we use a fast local store to avoid network delays.
"""

# Configuration via environment variables
QDRANT_URL = os.getenv("QDRANT_URL")  # No default to avoid accidental network calls
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_FORCE_STUB = os.getenv("QDRANT_STUB", "0").lower() in ("1", "true", "yes")


class _InMemoryQdrant:
    def __init__(self):
        self._collections: Dict[str, Dict[str, Any]] = {}

    def get_collection(self, name: str):
        if name not in self._collections:
            raise KeyError("not found")
        return self._collections[name]

    def recreate_collection(self, collection_name: str, vectors_config):
        self._collections[collection_name] = {
            "points": [],
            "size": getattr(vectors_config, "size", vectors_config.get("size", 0)) if hasattr(vectors_config, "size") or isinstance(vectors_config, dict) else 0,
        }

    def upsert(self, collection_name: str, points: List[Any]):
        col = self._collections.setdefault(collection_name, {"points": [], "size": 0})
        for p in points:
            # p may be PointStruct or dict
            point_id = getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else None)
            vector = getattr(p, "vector", None) or (p.get("vector") if isinstance(p, dict) else None)
            payload = getattr(p, "payload", None) or (p.get("payload") if isinstance(p, dict) else {})
            # replace if exists
            col["points"] = [q for q in col["points"] if q["id"] != point_id]
            col["points"].append({"id": point_id, "vector": vector, "payload": payload})

    class _Result:
        def __init__(self, points):
            self.points = points

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x*y for x, y in zip(a, b))
        na = math.sqrt(sum(x*x for x in a)) or 1.0
        nb = math.sqrt(sum(y*y for y in b)) or 1.0
        return dot / (na * nb)

    def query_points(self, collection_name: str, query: List[float], limit: int = 3):
        col = self._collections.get(collection_name, {"points": []})
        scored = []
        for p in col["points"]:
            score = self._cosine_sim(query, p.get("vector") or [])
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for _, p in scored[:limit]:
            # Minimal object with payload attribute
            hits.append(type("Hit", (), {"payload": p.get("payload", {}), "id": p.get("id"), "vector": p.get("vector")}))
        return self._Result(hits)

    def search(self, collection_name: str, query_vector: List[float], limit: int = 3):
        # Return list of hits similar to qdrant-client
        return self.query_points(collection_name, query_vector, limit).points


def _make_real_client():
    # Only create a real client when explicitly configured to avoid timeouts
    if not (QDRANT_SDK_AVAILABLE and QDRANT_URL):
        return None
    try:
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=1.0)
    except Exception:
        return None


qdrant_client = _InMemoryQdrant() if (QDRANT_FORCE_STUB or not QDRANT_URL) else (_make_real_client() or _InMemoryQdrant())


def _map_distance(distance: str):
    try:
        d = (distance or "cosine").strip().upper()
        if hasattr(qmodels, "Distance"):
            # qdrant_client.http.models.Distance
            if d.startswith("COS"):
                return qmodels.Distance.COSINE
            if d.startswith("EUC"):
                return qmodels.Distance.EUCLID
            if d.startswith("MAN") or d.startswith("DOT"):
                # Some SDKs expose DOT or MANHATTAN
                return getattr(qmodels.Distance, "DOT", qmodels.Distance.COSINE)
        return distance
    except Exception:
        return distance


def ensure_collection(collection_name: str, vector_size: int, distance: str = "Cosine") -> None:
    try:
        existing = qdrant_client.get_collection(collection_name)
        if existing:
            return
    except Exception:
        pass
    try:
        if QDRANT_SDK_AVAILABLE and not isinstance(qdrant_client, _InMemoryQdrant):
            # Newer qdrant-client expects Distance enum, and supports with_payload options in queries
            dist = _map_distance(distance)
            qdrant_client.recreate_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(size=vector_size, distance=dist),
            )
        else:
            qdrant_client.recreate_collection(collection_name, {"size": vector_size})
    except Exception:
        pass