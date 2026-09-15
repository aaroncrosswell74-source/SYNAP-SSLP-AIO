"""
Global Event Ledger - Canonical Ordering Substrate
==================================================

Provides a thread-safe, monotonic sequence allocator. 
Enforces a total-order execution invariant across async boundaries.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass(frozen=True)
class CognitiveEvent:
    global_seq: int
    cycle_id: str
    subsystem: str
    action: str
    payload: Dict[str, Any]
    seed: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global_seq": self.global_seq,
            "cycle_id": self.cycle_id,
            "subsystem": self.subsystem,
            "action": self.action,
            "payload": self.payload,
            "seed": self.seed,
            "timestamp": self.timestamp
        }

class GlobalEventLedger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure a uniform sequence authority across all modules."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GlobalEventLedger, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._seq = 0
        self._history: List[CognitiveEvent] = []
        self._initialized = True

    def emit(self, cycle_id: str, subsystem: str, action: str = '', payload: Dict[str, Any] = None, seed: int = 0, stage: str = '', metadata: Dict[str, Any] = None, sequence_delta: int = 0) -> int:
        """Allocates a global sequence index and writes the transition to the ledger."""
        with self._lock:
            self._seq += 1
            event = CognitiveEvent(
                global_seq=self._seq,
                cycle_id=cycle_id,
                subsystem=subsystem,
                action=action or stage,
                payload=payload or metadata or {},
                seed=seed or sequence_delta
            )
            self._history.append(event)
            return self._seq

    def get_sequence_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [ev.to_dict() for ev in self._history]

    def purge(self):
        with self._lock:
            self._seq = 0
            self._history.clear()

# Alias for import compatibility
GlobalEventLog = GlobalEventLedger
