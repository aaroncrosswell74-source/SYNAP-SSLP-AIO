"""
Circuit Breaker and Safe Recovery Actions.
"""

import logging
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

class CircuitBreakerFailover:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 5.0):
        self.threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self.failure_count = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF-OPEN

    def record_failure(self, state_snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Increments system crash indices and issues safe-state rollback frameworks if breached."""
        self.failure_count += 1
        logger.warning(f"Failover interface registered alert. Count: {self.failure_count}/{self.threshold}")
        
        if self.failure_count >= self.threshold:
            self.state = "OPEN"
            logger.critical("CIRCUIT BREAKER TRIPPED. Executing state rollback mechanisms.")
            return self._build_emergency_fallback(state_snapshot)
        return None

    def record_success(self):
        """Resets the circuit parameters once execution is clean."""
        self.failure_count = 0
        self.state = "CLOSED"

    def _build_emergency_fallback(self, crashed_state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "confidence_score": 0.0,
            "context": {"error_recovery_mode": True, "raw_dump": str(crashed_state.get("context", {}))},
            "convergence_reason": "failover_recovery_circuit_tripped"
        }