import os
import json

class ContextStore:
    def __init__(self, base_dir="context_store"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _context_filename(self, context_type, context_id):
        return os.path.join(self.base_dir, f"{context_type}_{context_id}.json")

    def get_context(self, context_type, context_id):
        path = self._context_filename(context_type, context_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def set_context(self, context_type, context_id, data):
        path = self._context_filename(context_type, context_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def list_contexts(self, context_type):
        files = os.listdir(self.base_dir)
        prefix = f"{context_type}_"
        return [f[len(prefix):-5] for f in files if f.startswith(prefix) and f.endswith(".json")] 