"""
Confidence Evaluation - Computes scalar confidence based on structural signals.
"""

import math
from typing import Dict, Any, List

def evaluate_confidence(
    raw_text: str,
    generation_metadata: Dict[str, Any],
    upulse_metrics: Dict[str, float]
) -> float:
    """
    Computes a structural confidence score bounded in [0.0, 1.0].
    
    Penalizes chaos signals (high arousal, low structural syntax compliance) 
    and rewards calm, highly structured syntactic formatting blocks.
    """
    if not raw_text or len(raw_text.strip()) == 0:
        return 0.0

    base_score = 0.8
    
    # 1. Structural/Formatting Checks (e.g., Markdown or tag validation)
    has_xml_tags = bool("<THOUGHT>" in raw_text or "<REFLECTION>" in raw_text)
    if has_xml_tags:
        base_score += 0.05
        
    # 2. Extract and penalize generation indicators (e.g., token repetition metrics)
    repetition_penalty = generation_metadata.get("repetition_index", 0.0)
    base_score -= min(0.3, repetition_penalty * 0.5)
    
    # 3. Incorporate internal system state from upulse (Arousal dampening)
    arousal = upulse_metrics.get("arousal", 0.5)
    if arousal > 0.7:
        # High arousal / stress degrades mechanical confidence
        base_score -= (arousal - 0.7) * 0.4

    return max(0.0, min(1.0, base_score))