"""
Relevance Scoring Substrate - Measures semantic target alignment.
"""

from typing import List, Set
import re

class RelevanceEvaluator:
    def __init__(self, stop_words: Set[str] = None):
        self.stop_words = stop_words or {"the", "and", "a", "of", "to", "in", "is", "that", "it"}

    def _tokenize_clean(self, text: str) -> List[str]:
        words = re.findall(r'\b[a-zA-Z]{3,15}\b', text.lower())
        return [w for w in words if w not in self.stop_words]

    def compute_relevance(self, generated_text: str, objective_text: str) -> float:
        """
        Calculates a primitive keyword overlap score bounded in [0.0, 1.0].
        Ensures the model generation is fundamentally answering the problem prompt.
        """
        gen_tokens = set(self._tokenize_clean(generated_text))
        obj_tokens = set(self._tokenize_clean(objective_text))

        if not obj_tokens:
            return 1.0  # Empty objective implies no context constraints
        if not gen_tokens:
            return 0.0

        overlap = gen_tokens.intersection(obj_tokens)
        # Ratio of matched required objective items
        return float(len(overlap) / len(obj_tokens))