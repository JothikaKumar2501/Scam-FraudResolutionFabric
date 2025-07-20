import os
import json
from typing import Any, Dict, Optional

CONTEXT_DIR = 'context_store'

os.makedirs(CONTEXT_DIR, exist_ok=True)

def save_context(context_type: str, context_id: str, data: Dict[str, Any]):
    path = os.path.join(CONTEXT_DIR, f'{context_type}_{context_id}.json')
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def load_context(context_type: str, context_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(CONTEXT_DIR, f'{context_type}_{context_id}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

def list_contexts(context_type: str):
    files = [f for f in os.listdir(CONTEXT_DIR) if f.startswith(context_type+'_')]
    return [f.split('_', 1)[1].replace('.json', '') for f in files]

class ContextStore:
    """Simple in-memory context store for agentic system."""
    def __init__(self):
        self._store = {}
    def __getitem__(self, key):
        return self._store[key]
    def __setitem__(self, key, value):
        self._store[key] = value
    def get(self, key, default=None):
        return self._store.get(key, default)
    def items(self):
        return self._store.items() 