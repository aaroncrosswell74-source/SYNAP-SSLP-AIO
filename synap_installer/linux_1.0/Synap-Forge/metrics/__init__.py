"""
Consciousness Engine - Metrics Module
"""

from .clarity import (
    calculate_metrics,
    calculate_streaming_metrics,
    calculate_clarity_only,
    calculate_dominance_only
)

from .similarity import (
    cosine_similarity,
    batch_cosine_similarity
)

__all__ = [
    'calculate_metrics',
    'calculate_streaming_metrics',
    'calculate_clarity_only',
    'calculate_dominance_only',
    'cosine_similarity',
    'batch_cosine_similarity'
]
