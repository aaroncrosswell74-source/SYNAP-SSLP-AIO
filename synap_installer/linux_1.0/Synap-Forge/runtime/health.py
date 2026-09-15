"""
Unified health reporting - aggregates entropy, GPU pressure, contradiction load, etc.
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SystemHealthReport:
    """Aggregated system diagnostics - safe for serialization and replay."""
    entropy_index: float
    contradiction_load: float
    gpu_pressure: float
    scheduler_load: float
    stability_score: float
    requires_intervention: bool
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            object.__setattr__(self, "timestamp", time.time())


class HealthAggregator:
    """
    Aggregates metrics from various subsystems to produce a system health report.
    Does not import core/ or cognition/ - receives primitive values via update methods.
    """

    def __init__(self):
        self._entropy_index = 0.0
        self._contradiction_load = 0.0
        self._gpu_pressure = 0.0
        self._scheduler_load = 0.0

    def update_entropy(self, value: float) -> None:
        """Update current entropy index (0=stable, 1=collapse)."""
        self._entropy_index = max(0.0, min(1.0, value))

    def update_contradiction_load(self, value: float) -> None:
        """Update current contradiction load (0=none, 1=maximum)."""
        self._contradiction_load = max(0.0, min(1.0, value))

    def update_gpu_pressure(self, value: float) -> None:
        """Update GPU pressure (0=idle, 1=critical)."""
        self._gpu_pressure = max(0.0, min(1.0, value))

    def update_scheduler_load(self, value: float) -> None:
        """Update scheduler load (0=idle, 1=overloaded)."""
        self._scheduler_load = max(0.0, min(1.0, value))

    def get_report(self) -> SystemHealthReport:
        """Generate a health report from current aggregated values."""
        # Simple stability score: inverse of weighted sum of pressures
        weighted_pressure = (
            0.3 * self._entropy_index +
            0.3 * self._contradiction_load +
            0.2 * self._gpu_pressure +
            0.2 * self._scheduler_load
        )
        stability_score = max(0.0, min(1.0, 1.0 - weighted_pressure))
        requires_intervention = (
            self._entropy_index > 0.85 or
            self._contradiction_load > 0.8 or
            self._gpu_pressure > 0.9 or
            stability_score < 0.3
        )
        return SystemHealthReport(
            entropy_index=self._entropy_index,
            contradiction_load=self._contradiction_load,
            gpu_pressure=self._gpu_pressure,
            scheduler_load=self._scheduler_load,
            stability_score=stability_score,
            requires_intervention=requires_intervention,
        )
