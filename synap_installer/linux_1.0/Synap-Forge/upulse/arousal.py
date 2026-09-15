"""Arousal estimator - from lexical energy or physiological proxies."""

from typing import Set, List
from .valence import simple_tokenize

HIGH_AROUSAL_WORDS: Set[str] = {
    "excited", "angry", "passionate", "furious", "ecstatic", "thrilled",
    "rage", "wild", "fierce", "intense", "explosive", "burning",
    "screaming", "racing", "urgent", "desperate", "manic", "electric"
}
LOW_AROUSAL_WORDS: Set[str] = {
    "calm", "peaceful", "quiet", "still", "gentle", "soft", "sleepy",
    "relaxed", "serene", "tranquil", "slow", "steady", "cool", "mellow"
}


class ArousalEstimator:
    """Estimate arousal from lexical arousal words."""

    @staticmethod
    def from_text(text: str) -> float:
        words = simple_tokenize(text)
        if not words:
            return 0.5
        high = sum(1 for w in words if w in HIGH_AROUSAL_WORDS)
        low = sum(1 for w in words if w in LOW_AROUSAL_WORDS)
        total = len(words)
        raw = 0.5 + (high - low) / total
        return max(0.0, min(1.0, raw))

    @staticmethod
    def from_sentence_length_variance(text: str) -> float:
        """Longer, varied sentences → higher arousal."""
        import re
        sentences = re.split(r'[.!?]+', text)
        if len(sentences) <= 1:
            return 0.3
        lens = [len(s.split()) for s in sentences if s.strip()]
        if not lens:
            return 0.3
        mean_len = sum(lens) / len(lens)
        variance = sum((l - mean_len) ** 2 for l in lens) / len(lens)
        norm = min(1.0, variance / 25.0)
        return 0.3 + 0.5 * norm