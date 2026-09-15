"""
Time-Based Decay Functions - Configurable half-lives for different memory types

Default half-lives:
- Short-term (working memory): 1 hour (3600s)
- Long-term (semantic memory): 24 hours (86400s)  
- Emotional memory: 2 hours (7200s)
- Episodic buffer: 30 minutes (1800s)
"""

import math
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class DecayFunction:
    """
    Exponential decay function for time-based weighting
    
    Half-life examples:
    - 1800s (30 min): 50% weight after 30 minutes
    - 3600s (1 hour): 50% weight after 1 hour  
    - 7200s (2 hours): 50% weight after 2 hours
    - 86400s (24 hours): 50% weight after 1 day
    """
    
    def __init__(self, half_life: float = 7200.0):
        """
        Args:
            half_life: Time in seconds for weight to decay to 0.5
        """
        if half_life <= 0:
            raise ValueError(f"half_life must be > 0, got {half_life}")
        
        self.half_life = half_life
        self.decay_constant = math.log(2) / half_life
        logger.debug(f"DecayFunction: half_life={half_life}s, λ={self.decay_constant:.6f}")
    
    def calculate_weight(self, age_seconds: float) -> float:
        """
        Calculate decay weight for given age.
        
        Formula: weight = e^(-λ * age)
        - At age = half_life: weight = 0.5
        - At age = 2 * half_life: weight = 0.25
        - At age = 0: weight = 1.0
        """
        if age_seconds < 0:
            age_seconds = 0
        return float(math.exp(-self.decay_constant * age_seconds))
    
    def calculate_weights_batch(self, ages_seconds: List[float]) -> np.ndarray:
        """Vectorized weight calculation for multiple ages"""
        ages_array = np.array(ages_seconds)
        ages_array = np.maximum(ages_array, 0)
        return np.exp(-self.decay_constant * ages_array)
    
    def get_effective_age(self, timestamp: str, current_time: Optional[datetime] = None) -> float:
        """Calculate age in seconds from ISO timestamp"""
        event_time = datetime.fromisoformat(timestamp)
        reference_time = current_time or datetime.now()
        return max(0, (reference_time - event_time).total_seconds())
    
    def apply_decay_to_memories(self, memories: List[Dict], age_key: str = 'age', 
                                 score_key: str = 'score', weight_key: str = 'weight') -> List[Dict]:
        """Apply decay to memory scores based on age"""
        weighted = []
        for mem in memories:
            age = mem.get(age_key, 0)
            score = mem.get(score_key, 0.5)
            weight = self.calculate_weight(age)
            mem_copy = mem.copy()
            mem_copy[score_key] = score * weight
            mem_copy[weight_key] = weight
            weighted.append(mem_copy)
        return weighted
    
    def get_half_life_info(self) -> Dict[str, float]:
        """Get decay parameters and reference weights"""
        return {
            'half_life_seconds': self.half_life,
            'half_life_hours': self.half_life / 3600,
            'decay_constant': self.decay_constant,
            'weight_at_1_half_life': 0.5,
            'weight_at_2_half_lives': 0.25,
            'weight_at_3_half_lives': 0.125,
            'time_to_10_percent': -math.log(0.1) / self.decay_constant,
            'time_to_1_percent': -math.log(0.01) / self.decay_constant,
        }


# Preset decay functions for different memory types
class PresetDecay:
    """Pre-configured decay functions for common use cases"""
    
    @staticmethod
    def working_memory() -> DecayFunction:
        """30 minute half-life - for active conversation context"""
        return DecayFunction(half_life=1800)
    
    @staticmethod
    def emotional_memory() -> DecayFunction:
        """2 hour half-life - emotional states fade slower"""
        return DecayFunction(half_life=7200)
    
    @staticmethod
    def episodic_memory() -> DecayFunction:
        """4 hour half-life - recent events persist through session"""
        return DecayFunction(half_life=14400)
    
    @staticmethod
    def semantic_memory() -> DecayFunction:
        """24 hour half-life - learned patterns last longer"""
        return DecayFunction(half_life=86400)
    
    @staticmethod
    def long_term_memory() -> DecayFunction:
        """7 day half-life - important memories fade slowly"""
        return DecayFunction(half_life=604800)


def calculate_time_weight(age_seconds: float, half_life: float = 7200.0) -> float:
    """Standalone function for quick weight calculation"""
    decay = DecayFunction(half_life=half_life)
    return decay.calculate_weight(age_seconds)


def create_adaptive_decay(base_half_life: float = 3600.0, importance_multiplier: float = 5.0) -> DecayFunction:
    """Create decay with importance-based adjustment (more important = slower decay)"""
    adjusted_half_life = base_half_life * importance_multiplier
    return DecayFunction(half_life=adjusted_half_life)

class ActiveDecay:
    def __init__(self):
        self.importance_factors = {
            'recency': 0.3,
            'frequency': 0.2,
            'emotional_intensity': 0.15,
            'associative_breadth': 0.2,  # How many other memories connect to it
            'utility': 0.15  # How often it's been useful in past retrievals
        }
    
    def compute_importance(self, memory):
        # ML-based importance scoring
        features = self.extract_features(memory)
        importance = self.importance_model.predict(features)
        
        # Boost if memory has been accessed successfully before
        if memory.id in self.successful_retrievals:
            importance *= 1.5
            
        return importance * self.temporal_boost(memory.timestamp)