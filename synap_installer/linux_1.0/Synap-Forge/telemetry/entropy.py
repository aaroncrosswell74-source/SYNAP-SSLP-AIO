"""
Entropy Analytics - Measures information chaotic density in running loops.
"""

import math
from typing import List, Dict

class InformationEntropyCalculator:
    @staticmethod
    def calculate_token_distribution_entropy(token_counts: Dict[int, int]) -> float:
        """Computes information chaotic states within local tracking distributions."""
        total_tokens = sum(token_counts.values())
        if total_tokens == 0:
            return 0.0

        entropy_val = 0.0
        for count in token_counts.values():
            p_x = count / total_tokens
            if p_x > 0:
                entropy_val -= p_x * math.log2(p_x)
                
        return float(entropy_val)

    def calculate_signal_variance(self, state_history: List[float]) -> float:
        """Measures variance of continuous signals to catch feedback oscillations."""
        if len(state_history) < 2:
            return 0.0
        
        mean = sum(state_history) / len(state_history)
        variance = sum((x - mean) ** 2 for x in state_history) / len(state_history)
        return float(variance)