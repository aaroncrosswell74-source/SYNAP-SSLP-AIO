"""
Divergence Detection - Mathematical Substrate
==============================================

Identifies when a recursive process becomes unstable.

Divergence conditions:
    1. Confidence drops by more than `confidence_drop_threshold` (default 0.3)
    2. Feedback history oscillates beyond `feedback_range_threshold` (default 1.5)
    3. Context embedding collapses (norm < 0.01)

All inputs are primitive; no core imports.
"""

from typing import List, Any
import numpy as np


def check_divergence(
    old_state: Any,
    new_state: Any,
    confidence_drop_threshold: float = 0.3,
    feedback_history: List[float] = None,
    feedback_range_threshold: float = 1.5
) -> bool:
    """
    Pure function to detect divergence.

    Args:
        old_state: previous state
        new_state: current state
        confidence_drop_threshold: if new confidence is lower by this amount -> divergence
        feedback_history: list of recent feedback values (for oscillation check)
        feedback_range_threshold: max allowed range of recent feedback values

    Returns:
        True if divergence detected
    """
    # Condition 1: confidence drop
    if new_state.confidence_score < old_state.confidence_score - confidence_drop_threshold:
        return True

    # Condition 2: feedback oscillation
    if feedback_history and len(feedback_history) >= 3:
        recent = feedback_history[-3:]
        if max(recent) - min(recent) > feedback_range_threshold:
            return True

    # Condition 3: context collapse (embedding norm too small)
    if hasattr(new_state, 'context'):
        embedding = new_state.context.get('embedding')
        if embedding is not None:
            try:
                norm = np.linalg.norm(embedding)
                if norm < 0.01:
                    return True
            except:
                pass

    return False