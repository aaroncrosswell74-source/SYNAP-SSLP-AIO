"""
System Watchdog - detects stalls, deadlocks, and runaway recursion.
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuntimeHealth:
    """Snapshot of system health at a given moment."""
    heartbeat_age_ms: float
    active_channels: int
    stalled_channels: int
    recursion_depth: int
    entropy_index: float
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class RuntimeWatchdog:
    """
    Monitors runtime liveness and decides when to force an emergency reset.
    Uses a simple heartbeat mechanism.
    """

    def __init__(self, heartbeat_timeout_ms: int = 5000, stall_threshold_seconds: int = 30):
        self.heartbeat_timeout_ms = heartbeat_timeout_ms
        self.stall_threshold_seconds = stall_threshold_seconds
        self._last_heartbeat = time.time()
        self._active_channels = 0
        self._stalled_channels = 0
        self._recursion_depth = 0
        self._entropy_index = 0.0

    def pulse(self) -> None:
        """Call this periodically (e.g., from scheduler main loop) to mark liveness."""
        self._last_heartbeat = time.time()

    def detect_stall(self) -> bool:
        """Return True if no heartbeat within stall threshold."""
        elapsed_sec = time.time() - self._last_heartbeat
        return elapsed_sec > (self.stall_threshold_seconds)

    def should_emergency_reset(self) -> bool:
        """
        Emergency reset conditions:
        - Stall detected
        - Entropy index > 0.95 (collapse threshold)
        - Recursion depth beyond sane limit
        """
        if self.detect_stall():
            return True
        if self._entropy_index > 0.95:
            return True
        if self._recursion_depth > 20:
            return True
        return False

    def update_metrics(self, active_channels: int, stalled_channels: int,
                       recursion_depth: int, entropy_index: float) -> None:
        """Update internal metrics used for reset decisions."""
        self._active_channels = active_channels
        self._stalled_channels = stalled_channels
        self._recursion_depth = recursion_depth
        self._entropy_index = entropy_index

    def get_health_snapshot(self) -> RuntimeHealth:
        """Return current health snapshot."""
        return RuntimeHealth(
            heartbeat_age_ms=(time.time() - self._last_heartbeat) * 1000.0,
            active_channels=self._active_channels,
            stalled_channels=self._stalled_channels,
            recursion_depth=self._recursion_depth,
            entropy_index=self._entropy_index,
        )
