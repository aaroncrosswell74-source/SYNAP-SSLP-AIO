"""
GPU resource monitor - exposes safe primitive metrics only.
No tensor/device handles cross the boundary.
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GPUStats:
    """Immutable, serializable GPU metrics."""
    vram_used_mb: int
    vram_free_mb: int
    utilization_pct: float
    temperature_c: float
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            # Cannot assign to frozen dataclass directly; use object.__setattr__ in __new__
            object.__setattr__(self, "timestamp", time.time())


class GPUWatchdog:
    """
    Monitors GPU pressure and provides throttling recommendations.
    Actual hardware queries should be implemented in a subclass.
    """

    def __init__(self, memory_critical_threshold_mb: int = 1024, utilization_critical: float = 95.0):
        self.memory_critical_threshold_mb = memory_critical_threshold_mb
        self.utilization_critical = utilization_critical
        self._last_stats: Optional[GPUStats] = None

    def get_stats(self) -> GPUStats:
        """
        Retrieve current GPU metrics.
        Override this method with real hardware queries (e.g., via pynvml).
        Default implementation returns simulated safe values.
        """
        # Simulated values - replace with actual monitoring logic
        # Ensure returned values are primitive and safe.
        return GPUStats(
            vram_used_mb=4200,
            vram_free_mb=10100,
            utilization_pct=34.5,
            temperature_c=52.0,
        )

    def is_memory_critical(self, stats: Optional[GPUStats] = None) -> bool:
        """Return True if free VRAM is below critical threshold."""
        if stats is None:
            stats = self.get_stats()
        return stats.vram_free_mb < self.memory_critical_threshold_mb

    def recommend_batch_scale(self, stats: Optional[GPUStats] = None) -> float:
        """
        Recommend a scaling factor for batch/parallelism (0.0 = halt, 1.0 = full).
        Based on memory pressure and utilization.
        """
        if stats is None:
            stats = self.get_stats()
        if self.is_memory_critical(stats):
            return 0.0
        memory_free_ratio = stats.vram_free_mb / (stats.vram_used_mb + stats.vram_free_mb + 1)
        util_penalty = max(0.0, (stats.utilization_pct - 75.0) / 25.0)
        scale = memory_free_ratio * (1.0 - util_penalty)
        return max(0.0, min(1.0, scale))
