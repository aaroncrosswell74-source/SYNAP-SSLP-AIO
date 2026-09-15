"""
Processing State Schema
=======================

Immutable state object that flows through the processing pipeline.
Each stage reads the state and returns a modified copy.

Schema:
    Input:
        - raw_input: str            : Original user query
        - context: Dict             : Additional context from memory/history
        - timestamp: str            : ISO format timestamp
    
    Stage Flags:
        - noise_filtered: bool      : Input preprocessing complete
        - patterns_generated: bool  : Candidate patterns created
        - coherence_maintained: bool: Stability checks passed
        - invalid_patterns_removed: bool : Pruning complete
    
    Coefficients:
        - snr_boost: float         : Signal-to-noise improvement (0-1)
        - novelty_coefficient: float: Pattern diversity (0-1)
        - stability_coefficient: float: Coherence strength (0-1)
        - bias_reduction: float    : Bias removal factor (0-1)
    
    Output:
        - processed_output: str    : Final refined output
        - confidence_score: float  : Output confidence (0-1)

Thread Safety:
    State objects are immutable after creation. Use replace() to create
    modified copies in each pipeline stage.

Example:
    state = ProcessingState(
        raw_input="Explain consciousness",
        context={"user_id": "u123"}
    )
    
    # Stage modifies and returns new state
    new_state = state.replace(noise_filtered=True, snr_boost=0.15)
"""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


@dataclass(frozen=True)
class ProcessingState:
    """Immutable state object for pipeline processing"""
    
    # Input
    raw_input: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    pipeline_stages: tuple = field(default_factory=tuple)
    
    # Stage 1: Input Filter
    noise_filtered: bool = False
    input_normalized: bool = False
    snr_boost: float = 0.0
    
    # Stage 2: Pattern Generator
    patterns_generated: bool = False
    solution_space_explored: bool = False
    novelty_coefficient: float = 0.0
    
    # Stage 3: Coherence Controller
    coherence_maintained: bool = False
    stability_coefficient: float = 0.0
    
    # Stage 4: Output Refiner
    invalid_patterns_removed: bool = False
    bias_reduction: float = 0.0
    
    # Final output
    processed_output: Optional[str] = None
    confidence_score: float = 0.0
    recursion_depth: int = 0
    convergence_reason: Optional[str] = None
    feedback_history: List[float] = field(default_factory=list)
    state_history: List[Any] = field(default_factory=list)
    timed_out: bool = False
    
    def replace(self, **changes) -> 'ProcessingState':
        """Create modified copy of state (immutable pattern)"""
        return replace(self, **changes)
    
    def add_stage(self, stage_name: str) -> 'ProcessingState':
        """Add stage to pipeline history"""
        new_stages = self.pipeline_stages + (stage_name,)
        return self.replace(pipeline_stages=new_stages)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'raw_input': self.raw_input,
            'context': self.context,
            'timestamp': self.timestamp,
            'pipeline_stages': list(self.pipeline_stages),
            'noise_filtered': self.noise_filtered,
            'input_normalized': self.input_normalized,
            'snr_boost': self.snr_boost,
            'patterns_generated': self.patterns_generated,
            'solution_space_explored': self.solution_space_explored,
            'novelty_coefficient': self.novelty_coefficient,
            'coherence_maintained': self.coherence_maintained,
            'stability_coefficient': self.stability_coefficient,
            'invalid_patterns_removed': self.invalid_patterns_removed,
            'bias_reduction': self.bias_reduction,
            'processed_output': self.processed_output,
            'confidence_score': self.confidence_score,
            'convergence_reason': self.convergence_reason,
            'feedback_history': self.feedback_history,
            'recursion_depth': self.recursion_depth,
            'timed_out': self.timed_out
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingState':
        """Deserialize from dictionary"""
        # Convert list back to tuple for pipeline_stages
        if 'pipeline_stages' in data:
            data['pipeline_stages'] = tuple(data['pipeline_stages'])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ProcessingState':
        """Deserialize from JSON string"""
        return cls.from_dict(json.loads(json_str))
    
    def get_stage_summary(self) -> str:
        """Human-readable pipeline summary"""
        stages = " → ".join(self.pipeline_stages) if self.pipeline_stages else "No stages"
        return f"Pipeline: {stages}\nConfidence: {self.confidence_score:.2f}"


def create_initial_state(user_input: str, context: Optional[Dict] = None) -> ProcessingState:
    """
    Factory function for creating initial processing state
    
    Args:
        user_input: Raw user query
        context: Optional context dictionary
    
    Returns:
        Fresh ProcessingState ready for pipeline
    """
    return ProcessingState(
        raw_input=user_input,
        context=context or {}
    )
