"""
Contradiction Detection - Flags logical collisions within local processing frames.
"""

from typing import List

class ContradictionDetector:
    def __init__(self, baseline_triggers: List[str] = None):
        self.triggers = baseline_triggers or [
            ("override", "preserve"),
            ("converged", "diverged"),
            ("valid", "invalid"),
            ("execute", "abort")
        ]

    def scan_for_collisions(self, current_thought: str, previous_thought: str) -> float:
        """
        Scans for localized logical contradictions.
        Returns a collision coefficient from 0.0 (harmonious) to 1.0 (deadlocked conflict).
        """
        c_lower = current_thought.lower()
        p_lower = previous_thought.lower()
        
        collision_weight = 0.0
        
        for term_a, term_b in self.triggers:
            # Check if processing states flipflopped entirely on core assertions
            if (term_a in c_lower and term_b in p_lower) or (term_b in c_lower and term_a in p_lower):
                collision_weight += 0.35
                
        return min(1.0, collision_weight)