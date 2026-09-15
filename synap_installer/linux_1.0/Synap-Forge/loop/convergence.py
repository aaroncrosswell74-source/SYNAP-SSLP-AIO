"""
Convergence Detection - Mathematical Substrate
===============================================

Determines whether a recursive process has stabilised.

Formula:
    weighted_delta = Σ(w_i * |new_attr_i - old_attr_i|)
    converged = weighted_delta < threshold

Attributes considered:
    - confidence_score (weight 0.4)
    - stability_coefficient (if available, weight 0.3)
    - clarity_score (if available, weight 0.2)
    - context embedding similarity (if available, weight 0.1)

All inputs are primitive numbers; no core imports.
"""

from typing import Any
import numpy as np


def check_convergence(
    old_state: Any,
    new_state: Any,
    threshold: float = 0.01
) -> bool:
    """
    Pure function to check if two states are converged.

    Args:
        old_state: previous state (any object with numeric attributes)
        new_state: current state
        threshold: maximum allowed weighted delta (default 0.01)

    Returns:
        True if weighted change < threshold
    """
    metrics = []
    weights = []

    # Confidence (always present)
    conf_delta = abs(new_state.confidence_score - old_state.confidence_score)
    metrics.append(conf_delta)
    weights.append(0.4)

    # Stability coefficient
    if hasattr(old_state, 'stability_coefficient') and hasattr(new_state, 'stability_coefficient'):
        stab_delta = abs((new_state.stability_coefficient or 0.0) - (old_state.stability_coefficient or 0.0))
        metrics.append(stab_delta)
        weights.append(0.3)

    # Clarity score
    if hasattr(old_state, 'clarity_score') and hasattr(new_state, 'clarity_score'):
        clarity_delta = abs((new_state.clarity_score or 0.0) - (old_state.clarity_score or 0.0))
        metrics.append(clarity_delta)
        weights.append(0.2)

    # Context embedding similarity
    if hasattr(old_state, 'context') and hasattr(new_state, 'context'):
        old_emb = old_state.context.get('embedding')
        new_emb = new_state.context.get('embedding')
        if old_emb is not None and new_emb is not None:
            try:
                old_vec = np.array(old_emb)
                new_vec = np.array(new_emb)
                norm_old = np.linalg.norm(old_vec)
                norm_new = np.linalg.norm(new_vec)
                if norm_old > 0 and norm_new > 0:
                    similarity = np.dot(old_vec, new_vec) / (norm_old * norm_new)
                    context_delta = 1.0 - similarity
                    metrics.append(context_delta)
                    weights.append(0.1)
            except:
                pass

    if not metrics:
        return False

    # Normalise weights
    total = sum(weights)
    if total > 0:
        weights = [w / total for w in weights]
    weighted_delta = sum(m * w for m, w in zip(metrics, weights))

    return weighted_delta < threshold