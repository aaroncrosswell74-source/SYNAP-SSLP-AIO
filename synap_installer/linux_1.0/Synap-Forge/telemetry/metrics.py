"""
Metrics Aggregation Substrate - Time-series rolling scalar logs.
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple  # Optional added

@dataclass(frozen=True)
class TimeSeriesMetric:
    timestamp: float
    value: float
    tags: Tuple[Tuple[str, str], ...]

class MetricsCollector:
    def __init__(self, max_history_len: int = 1000):
        self.max_history = max_history_len
        self.registry: Dict[str, List[TimeSeriesMetric]] = {}

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Logs a variable scalar metric value to historical telemetry charts."""
        if name not in self.registry:
            self.registry[name] = []
            
        tag_tuple = tuple(tags.items()) if tags else ()
        metric_point = TimeSeriesMetric(timestamp=time.time(), value=float(value), tags=tag_tuple)
        
        history = self.registry[name]
        history.append(metric_point)
        
        if len(history) > self.max_history:
            history.pop(0)

    def get_average(self, name: str) -> float:
        """Returns mathematical moving averages for designated metric strings."""
        history = self.registry.get(name, [])
        if not history:
            return 0.0
        return sum(pt.value for pt in history) / len(history)