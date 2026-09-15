"""
Semantic Drift Analyzer - Tracks topic degradation across recursive cycles.
"""

import re
from typing import Set

class DriftAnalyzer:
    @staticmethod
    def _extract_keywords(text: str) -> Set[str]:
        """Extracts simple alphanumeric keyword vectors for dependency-free text intersection."""
        return set(re.findall(r'\b[a-zA-Z]{4,12}\b', text.lower()))

    def calculate_drift(self, anchor_context: str, current_context: str) -> float:
        """
        Measures structural Jaccard distance metrics between token keywords.
        0.0 = aligned; 1.0 = completely unanchored word drift.
        """
        words_anchor = self._extract_keywords(anchor_context)
        words_current = self._extract_keywords(current_context)

        if not words_anchor or not words_current:
            return 1.0

        intersection = words_anchor.intersection(words_current)
        union = words_anchor.union(words_current)

        jaccard_similarity = len(intersection) / len(union)
        return float(1.0 - jaccard_similarity)