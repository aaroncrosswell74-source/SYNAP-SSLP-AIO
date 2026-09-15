"""
uPulse - Emotional core for Lyra.
Provides affect, valence, arousal, emotional decay, and emotion‑tagged memory.
"""
from .coversation_scoring import ConversationProcessor, ImportanceScorer
from . import affect
from . import valence
from . import arousal
# from . import observer_pulse  # TODO: fix indentation

__all__ = [
    "ConversationProcessor",
    "ImportanceScorer",
    "affect",
    "valence",
    "arousal",
    "observer_pulse",
]