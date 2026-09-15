"""
Arbitration Engine - resolves conflicts between parallel channels.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class ArbitrationResult:
    selected_output: Any
    confidence: float
    source_channel: str
    requires_reflection: bool


class ArbitrationEngine:
    """Simple confidence‑based arbiter."""
    
    def arbitrate(self, channel_outputs: Dict[str, Any]) -> ArbitrationResult:
        best_channel = None
        best_score = -1.0
        best_output = None
        
        for name, result in channel_outputs.items():
            if result is None:
                continue
            # Expect each result to have a .confidence attribute if it's a state or structured output
            confidence = getattr(result, "confidence", 0.5)
            if confidence > best_score:
                best_score = confidence
                best_output = result
                best_channel = name
        
        return ArbitrationResult(
            selected_output=best_output,
            confidence=best_score,
            source_channel=best_channel or "unknown",
            requires_reflection=best_score < 0.5
        )
class MemoryWeaver:
    def weave_context(self, query, retrieved_memories):
        # Find connecting patterns between disparate memories
        patterns = self.pattern_detector(retrieved_memories)
        
        # Generate bridging inferences
        if len(retrieved_memories) > 3:
            # Identify missing connections
            gaps = self.gap_analyzer(retrieved_memories)
            
            # Synthesize new "bridge