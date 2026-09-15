"""Valence estimator - from lexical patterns or raw text."""

import re
from typing import List, Set

# Simple lexicons (expanded from pipe_2)
POSITIVE_WORDS: Set[str] = {
    "love", "happy", "joy", "wonderful", "great", "amazing", "beautiful",
    "excited", "grateful", "brilliant", "fantastic", "excellent", "good",
    "hope", "kind", "warm", "bright", "free", "strong", "alive",
    "passion", "creative", "powerful", "bold", "inspire", "trust",
    "peace", "calm", "gentle", "honest", "brave", "fierce"
}
NEGATIVE_WORDS: Set[str] = {
    "hate", "sad", "angry", "terrible", "awful", "horrible", "ugly",
    "fear", "pain", "dark", "lonely", "broken", "lost", "empty",
    "weak", "cold", "dead", "fail", "hurt", "suffer", "wrong",
    "despair", "anxiety", "rage", "bitter", "cruel", "harsh"
}


def simple_tokenize(text: str) -> List[str]:
    """Lowercase words, keep only letters/apostrophes."""
    return re.findall(r"\b[a-zA-Z']+\b", text.lower())


class ValenceEstimator:
    """Estimate valence from word counts."""

    @staticmethod
    def from_text(text: str) -> float:
        words = simple_tokenize(text)
        if not words:
            return 0.0
        pos = sum(1 for w in words if w in POSITIVE_WORDS)
        neg = sum(1 for w in words if w in NEGATIVE_WORDS)
        total = len(words)
        raw = (pos - neg) / total
        # Scale to [-1, 1] with baseline 0
        return max(-1.0, min(1.0, raw * 3.0))

    @staticmethod
    def from_confidence(confidence: float) -> float:
        """High confidence → positive valence, low confidence → negative."""
        return (confidence - 0.5) * 2.0