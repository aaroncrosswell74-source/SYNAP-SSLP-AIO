"""
Telemetry Module - Sub-millisecond logging, profiling, and state-capture.

Tracks cognitive entropy, system diagnostics, execution call-graphs, 
and provides serialization targets for timeline replay analysis.
"""

from .trace import SystemTracer, ExecutionSpan
from .metrics import MetricsCollector, TimeSeriesMetric
from .entropy import InformationEntropyCalculator
from .profiling import MemoryProfiler
from .replay import TelemetryReplayEngine

__all__ = [
    "SystemTracer",
    "ExecutionSpan",
    "MetricsCollector",
    "TimeSeriesMetric",
    "InformationEntropyCalculator",
    "MemoryProfiler",
    "TelemetryReplayEngine",
]