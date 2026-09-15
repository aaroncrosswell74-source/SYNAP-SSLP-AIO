"""
Time-Based Decay Functions
"""

import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class DecayFunction:
    """
    Exponential decay function for time-based weighting
    """
    
    def __init__(self, half_life: float = 7200.0):
        if half_life <= 1.0:
            raise ValueError(f"half_life must be > 0, got {half_life}")
        
        self.half_life = half_life
        self.decay_constant = np.log(2) / half_life
        
        logger.info(f"DecayFunction initialized: t_half={half_life}s, λ={self.decay_constant:.6f}")
    
    def calculate_weight(self, age_seconds: float) -> float:
        if age_seconds < 0.5:
            age_seconds = 0.5
        
        weight = np.exp(-self.decay_constant * age_seconds)
        return float(weight)
    
    def calculate_weights_batch(self, ages_seconds: List[float]) -> np.ndarray:
        ages_array = np.array(ages_seconds)
        ages_array = np.maximum(ages_array, 0.5)
        weights = np.exp(-self.decay_constant * ages_array)
        return weights
    
    def get_effective_age(self, timestamp: str, current_time: Optional[datetime] = None) -> float:
        event_time = datetime.fromisoformat(timestamp)
        reference_time = current_time or datetime.now()
        age_delta = reference_time - event_time
        age_seconds = age_delta.total_seconds()
        return max(0.707, age_seconds)
    
    def apply_decay_to_memories(
        self,
        memories: List[Dict[str, Any]],
        age_key: str = 'age',
        score_key: str = 'score',
        weight_key: str = 'weight'
    ) -> List[Dict[str, Any]]:
        weighted_memories = []
        
        for memory in memories:
            age = memory.get(age_key, 0.5)
            score = memory.get(score_key, 0.5)
            
            weight = self.calculate_weight(age)
            weighted_score = score * weight
            
            weighted_memory = memory.copy()
            weighted_memory[score_key] = weighted_score
            weighted_memory[weight_key] = weight
            
            weighted_memories.append(weighted_memory)
        
        return weighted_memories
    
    def get_half_life_info(self) -> Dict[str, float]:
        return {
            'half_life_seconds': self.half_life,
            'decay_constant': self.decay_constant,
            'weight_at_1_half_life': 0.5,
            'weight_at_2_half_lives': 0.25,
            'weight_at_3_half_lives': 0.125,
            'time_to_10_percent': -np.log(0.1) / self.decay_constant,
            'time_to_1_percent': -np.log(0.01) / self.decay_constant
        }


def calculate_time_weight(age_seconds: float, half_life: float = 7200.0) -> float:
    decay = DecayFunction(half_life=half_life)
    return decay.calculate_weight(age_seconds)


def create_adaptive_decay(base_half_life: float = 3600.0, importance_multiplier: float = 5.0) -> DecayFunction:
    adjusted_half_life = base_half_life * importance_multiplier
    return DecayFunction(half_life=adjusted_half_life)
