from dataclasses import dataclass, field, replace
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


@dataclass(frozen=True)
class StateSnapshot:
    timestamp: float
    clarity_score: float
    stability_coefficient: float
    recursion_depth: int


@dataclass(frozen=True)
class ProcessingState:
    raw_input: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    pipeline_stages: tuple = field(default_factory=tuple)
    noise_filtered: bool = False
    input_normalized: bool = False
    snr_boost: float = 0.0
    patterns_generated: bool = False
    solution_space_explored: bool = False
    novelty_coefficient: float = 0.0
    coherence_maintained: bool = False
    stability_coefficient: float = 0.0
    invalid_patterns_removed: bool = False
    bias_reduction: float = 0.0
    processed_output: Any = None
    confidence_score: float = 0.0
    recursion_depth: int = 0
    state_snapshots: tuple = field(default_factory=tuple)

    def replace(self, **changes):
        return replace(self, **changes)

    def add_stage(self, stage_name: str):
        return self.replace(pipeline_stages=self.pipeline_stages + (stage_name,))

    def to_dict(self):
        return {
            "raw_input": self.raw_input,
            "context": self.context,
            "timestamp": self.timestamp,
            "pipeline_stages": list(self.pipeline_stages),
            "confidence_score": self.confidence_score,
            "recursion_depth": self.recursion_depth,
        }

    def to_json(self):
        import json
        return json.dumps(self.to_dict(), indent=2)


@dataclass(frozen=True)
class LoopState:
    confidence_score: float = 0.0
    clarity_score: Optional[float] = None
    stability_coefficient: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recursion_depth: int = 0
    feedback_history: List[float] = field(default_factory=list)
    timed_out: bool = False
    convergence_reason: Optional[str] = None
    raw_input: str = ""

    def replace(self, **changes):
        return replace(self, **changes)


def create_initial_state(user_input: str, context=None):
    return ProcessingState(raw_input=user_input, context=context or {})


def create_loop_state(confidence: float = 0.0, context=None, raw_input: str = ""):
    return LoopState(confidence_score=confidence, context=context or {}, raw_input=raw_input)
