"""
Uncertainty Substrate - Measures systemic processing entropy.
"""

import math
from typing import List

class UncertaintyCalculator:
    @staticmethod
    def calculate_shannon_entropy(probabilities: List[float]) -> float:
        """Calculates $H(X) = -\\sum P(x) \\log_2 P(x)$ to evaluate output distribution token chaos."""
        valid_probs = [p for p in probabilities if p > 0.0]
        total = sum(valid_probs)
        if total == 0:
            return 0.0
            
        # Normalize distribution
        norm_probs = [p / total for p in valid_probs]
        return -sum(p * math.log2(p) for p in norm_probs)

    def evaluate_state_uncertainty(self, performance_deltas: List[float]) -> float:
        """Evaluates how erratic the internal system vectors are changing across loops."""
        if not performance_deltas:
            return 1.0
            
        variance = sum((x - (sum(performance_deltas) / len(performance_deltas))) ** 2 for x in performance_deltas)
        normalized_variance = min(1.0, variance / max(1, len(performance_deltas)))
        return float(normalized_variance)