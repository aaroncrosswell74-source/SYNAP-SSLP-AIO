"""
Execution Tracing Substrate - Captures hierarchy-aware span durations.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ExecutionSpan:
    def __init__(self, name: str, parent_id: Optional[str] = None):
        self.span_id = str(uuid.uuid4())[:8]
        self.parent_id = parent_id
        self.name = name
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.metadata: Dict[str, Any] = {}

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        duration = (self.end_time - self.start_time) * 1000.0  # ms
        logger.debug(f"[SPAN] {self.name} ({self.span_id}) completed in {duration:.2f}ms")

class SystemTracer:
    def __init__(self):
        self.completed_spans: List[Dict[str, Any]] = []
        self.active_parent_id: Optional[str] = None

    def start_span(self, name: str) -> ExecutionSpan:
        """Spawns an execution tracking frame linked to any existing active parent."""
        span = ExecutionSpan(name, parent_id=self.active_parent_id)
        self.active_parent_id = span.span_id
        return span

    def close_span(self, span: ExecutionSpan, metadata: Optional[Dict[str, Any]] = None):
        """Concludes timing metrics collection and archives the span to disk/memory profiles."""
        if span.end_time == 0.0:
            span.end_time = time.perf_counter()
        
        span_data = {
            "span_id": span.span_id,
            "parent_id": span.parent_id,
            "name": span.name,
            "latency_ms": (span.end_time - span.start_time) * 1000.0,
            "metadata": metadata or {}
        }
        self.completed_spans.append(span_data)
        self.active_parent_id = span.parent_id

    def clear_traces(self):
        self.completed_spans.clear()
        self.active_parent_id = None