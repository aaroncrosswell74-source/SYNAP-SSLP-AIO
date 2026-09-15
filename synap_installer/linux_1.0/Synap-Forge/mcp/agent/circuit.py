"""Circuit breaker for external dependencies"""

import time
import logging
from typing import Dict, Tuple
from .config import CIRCUIT_BREAKER_FAILURES, CIRCUIT_BREAKER_WINDOW, CIRCUIT_BREAKER_TIMEOUT

logger = logging.getLogger("CircuitBreaker")

class CircuitBreaker:
    """Circuit breaker for MCP and Model calls"""
    
    def __init__(self):
        self._state: Dict[str, Dict] = {}
    
    def record_success(self, name: str):
        """Record a successful call"""
        if name not in self._state:
            self._state[name] = {"failures": 0, "last_failure": 0, "open_until": 0}
        self._state[name]["failures"] = 0
    
    def record_failure(self, name: str):
        """Record a failed call"""
        if name not in self._state:
            self._state[name] = {"failures": 0, "last_failure": 0, "open_until": 0}
        
        state = self._state[name]
        now = time.time()
        
        # Reset if outside window
        if now - state["last_failure"] > CIRCUIT_BREAKER_WINDOW:
            state["failures"] = 0
        
        state["failures"] += 1
        state["last_failure"] = now
        
        if state["failures"] >= CIRCUIT_BREAKER_FAILURES:
            state["open_until"] = now + CIRCUIT_BREAKER_TIMEOUT
            logger.warning(f"Circuit breaker OPEN for {name} (failures: {state['failures']})")
    
    def is_allowed(self, name: str) -> bool:
        """Check if the circuit is closed"""
        if name not in self._state:
            self._state[name] = {"failures": 0, "last_failure": 0, "open_until": 0}
        
        state = self._state[name]
        now = time.time()
        
        if state["open_until"] > now:
            # Circuit is open
            if now > state["open_until"]:
                # Half-open - allow one test
                state["open_until"] = 0
                logger.info(f"Circuit breaker HALF-OPEN for {name}")
                return True
            return False
        
        return True

# Singleton instance
_circuit_breaker = None

def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
