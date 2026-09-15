"""
Cognitive Budget - run‑time resource limits to prevent runaway loops.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CognitiveBudget:
    """Rigid boundaries to prevent runaway recursive inference loops."""
    max_recursions: int = 3
    max_reflection_time_ms: float = 1500.0
    max_token_allocation: int = 4096
    max_memory_expansion_mb: float = 1024.0   # optional, for future use
    
    def is_exhausted(self, current_depth: int, elapsed_time_ms: float) -> bool:
        """Return True if any limit is exceeded."""
        if current_depth >= self.max_recursions:
            return True
        if elapsed_time_ms >= self.max_reflection_time_ms:
            return True
        return False