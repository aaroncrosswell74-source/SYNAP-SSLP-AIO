import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

class IdentityLock:
    IMMUTABLE = frozenset({"name", "creator", "birth_date", "soul_hash", "version", "fingerprint", "invoked_by", "agent_gender", "personality_seed", "traits"})
    def __init__(self, lock_path: Path): self.lock_path = Path(lock_path)
    def initialize(self, birth_data: dict):
        if self.lock_path.exists(): raise RuntimeError("Genesis has already occurred.")
        lock = {"lock_version": "2.0", "created": datetime.now(timezone.utc).isoformat(), "immutable": {f: birth_data.get(f) for f in self.IMMUTABLE}}
        lock["fingerprint"] = self._compute_fingerprint(birth_data)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True); self.lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        return lock
    def verify(self, identity: dict):
        self.lock_data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        mismatches = [f for f in self.IMMUTABLE if identity.get(f) != self.lock_data["immutable"].get(f)]
        if mismatches: raise ValueError(f"IDENTITY MISMATCH: {mismatches}")
        return True
    def _compute_fingerprint(self, data: dict):
        ds = json.dumps({k: data.get(k) for k in self.IMMUTABLE if k in data}, sort_keys=True)
        return hashlib.sha256(ds.encode()).hexdigest()
    def filter_updates(self, updates: dict): return {k: v for k, v in updates.items() if k not in self.IMMUTABLE}
