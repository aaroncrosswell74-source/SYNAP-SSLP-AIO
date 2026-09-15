"""Idempotency store for preventing duplicate tool executions."""

import time
import hashlib
import threading
from typing import Any, Optional


class IdempotencyStore:
    """Simple in-memory idempotency cache."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)

            if item is None:
                return None

            value, timestamp = item

            if time.time() - timestamp > self.ttl:
                del self._store[key]
                return None

            return value

    def set(self, key: str, value: Any):
        with self._lock:
            self._store[key] = (value, time.time())

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self):
        with self._lock:
            self._store.clear()

    def is_duplicate(self, tool_name: str, arguments: dict, request_id: str) -> bool:
        """Check if this tool call has been executed before."""
        key = self._make_key(tool_name, arguments, request_id)
        return self.get(key) is not None

    def mark_executed(self, tool_name: str, arguments: dict, request_id: str, result: dict):
        """Mark a tool call as executed."""
        key = self._make_key(tool_name, arguments, request_id)
        self.set(key, {
            "result": result,
            "timestamp": time.time()
        })

    def _make_key(self, tool_name: str, arguments: dict, request_id: str) -> str:
        """Generate a consistent key for tool execution tracking."""
        # Sort arguments for consistent hashing
        args_str = str(sorted(arguments.items()))
        return f"{tool_name}:{hashlib.sha256(args_str.encode()).hexdigest()[:16]}:{request_id}"


# Global instance
_store = IdempotencyStore()


def get_idempotency_store() -> IdempotencyStore:
    """Return global idempotency store."""
    return _store
