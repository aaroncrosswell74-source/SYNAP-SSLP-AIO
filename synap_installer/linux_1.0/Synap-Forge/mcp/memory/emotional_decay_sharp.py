# emotional_decay.py - Complete emotional decay system
"""
Emotional Decay System - Both original and SHARP versions
==========================================================
"""

import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
import json

# Setup logger
logger = logging.getLogger(__name__)


# ============================================================================
# ORIGINAL EmotionalDecay class (for backward compatibility)
# ============================================================================

class EmotionalDecay:
    """Time‑based decay of emotional intensity (exponential)."""

    def __init__(self, half_life_seconds: float = 3600.0):
        self.half_life = half_life_seconds
        self.decay_constant = math.log(2) / half_life_seconds

    def weight(self, age_seconds: float) -> float:
        """Return decay weight in [0,1]."""
        if age_seconds < 0:
            age_seconds = 0.0
        return math.exp(-self.decay_constant * age_seconds)

    def apply_to_affect(self, valence: float, arousal: float,
                        timestamp: datetime, now: datetime) -> tuple:
        age = (now - timestamp).total_seconds()
        w = self.weight(age)
        return valence * w, arousal * w

    def get_stats(self) -> Dict[str, Any]:
        return {
            "half_life_seconds": self.half_life,
            "decay_constant": self.decay_constant,
            "weight_after_1hl": 0.5,
            "weight_after_2hl": 0.25,
        }


# ============================================================================
# SHARP EmotionalDecay - Enhanced version
# ============================================================================

class EmotionalState(Enum):
    """Emotional states with decay modifiers"""
    HIGH_AROUSAL = "high_arousal"      # Decays faster (excitement fades)
    LOW_AROUSAL = "low_arousal"         # Decays slower (calm persists)
    POSITIVE_VALENCE = "positive"       # Decays slower (happy memories persist)
    NEGATIVE_VALENCE = "negative"       # Decays faster (trauma fades)
    NEUTRAL = "neutral"                 # Normal decay


class SharpEmotionalDecay:
    """
    Enhanced emotional decay with:
    - Emotional state-specific decay rates
    - Circadian rhythm integration
    - Memory consolidation boosting
    - Trauma flashback prevention
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        
        # Base decay rates by emotion
        self.emotion_decay_rates = {
            EmotionalState.HIGH_AROUSAL: 1.5,    # Faster decay
            EmotionalState.LOW_AROUSAL: 0.7,      # Slower decay
            EmotionalState.POSITIVE_VALENCE: 0.8, # Slower decay
            EmotionalState.NEGATIVE_VALENCE: 1.3, # Faster decay
            EmotionalState.NEUTRAL: 1.0,          # Normal
        }
        
        # Circadian rhythm factors (hours of day)
        self.circadian_factors = self._build_circadian_factors()
        
        # Memory consolidation schedule (hours after encoding)
        self.consolidation_window = 8  # hours
        
        logger.info("✅ SharpEmotionalDecay initialized")
    
    def _default_config(self) -> Dict:
        return {
            "base_half_life_hours": 2.0,
            "decay_temperature": 0.5,
            "circadian_influence": 0.3,
            "consolidation_boost": 0.5,
            "trauma_threshold": 0.8,
            "reinforcement_rate": 0.1,
        }
    
    def _build_circadian_factors(self) -> Dict[int, float]:
        """Build circadian rhythm factors by hour of day"""
        factors = {}
        for hour in range(24):
            hour_normalized = hour / 24.0
            rhythm = math.sin((hour_normalized - 9/24) * 2 * math.pi) * 0.5 + 0.5
            evening_peak = math.sin((hour_normalized - 19/24) * 2 * math.pi) * 0.3 + 0.3
            factors[hour] = 0.7 + (rhythm * 0.3) + (evening_peak * 0.1)
            factors[hour] = min(1.0, factors[hour])
        return factors
    
    def calculate_decay(self, valence: float, arousal: float, 
                       timestamp: datetime, now: Optional[datetime] = None) -> Dict[str, float]:
        """
        Calculate emotional decay factors
        """
        now = now or datetime.now()
        age_hours = (now - timestamp).total_seconds() / 3600
        
        state = self._determine_state(valence, arousal)
        base_rate = self.emotion_decay_rates.get(state, 1.0)
        circadian_factor = self.circadian_factors.get(now.hour, 0.8)
        
        consolidation = 1.0
        if age_hours < self.consolidation_window:
            consolidation = 1.0 + (self.config["consolidation_boost"] * 
                                 (1 - age_hours / self.consolidation_window))
        
        effective_rate = base_rate * (1 - (circadian_factor * self.config["circadian_influence"]))
        effective_rate /= consolidation
        
        half_life = self.config["base_half_life_hours"] / effective_rate
        decay_weight = math.exp(-math.log(2) * age_hours / half_life)
        decay_weight = max(0.01, min(1.0, decay_weight))
        
        return {
            "decay_weight": decay_weight,
            "effective_half_life": half_life,
            "effective_rate": effective_rate,
            "emotional_state": state.value,
            "circadian_factor": circadian_factor,
            "age_hours": age_hours,
            "consolidation_factor": consolidation,
            "valence_decayed": valence * decay_weight,
            "arousal_decayed": arousal * decay_weight,
            "memory_strength": 1.0 - (1.0 - decay_weight) * 0.5
        }
    
    def _determine_state(self, valence: float, arousal: float) -> EmotionalState:
        """Determine emotional state from valence and arousal"""
        if arousal > 0.7:
            return EmotionalState.HIGH_AROUSAL
        elif arousal < 0.3:
            return EmotionalState.LOW_AROUSAL
        elif valence > 0.3:
            return EmotionalState.POSITIVE_VALENCE
        elif valence < -0.3:
            return EmotionalState.NEGATIVE_VALENCE
        else:
            return EmotionalState.NEUTRAL
    
    def apply_trauma_protection(self, memory: Dict, threshold: float = 0.8) -> Dict:
        """Apply trauma protection to prevent overwhelming memories"""
        valence = memory.get("valence", 0)
        if abs(valence) < threshold:
            return memory
        
        memory["decay_boost"] = 1.5
        memory["trauma_tag"] = True
        memory["processing_required"] = True
        
        if "arousal" in memory:
            memory["arousal"] = memory["arousal"] * 0.7
        
        return memory
    
    def get_emotional_profile(self, memories: List[Dict]) -> Dict[str, float]:
        """Get emotional profile of a set of memories"""
        if not memories:
            return {"avg_valence": 0, "avg_arousal": 0, "distribution": {}}
        
        valences = [m.get("valence", 0) for m in memories if "valence" in m]
        arousals = [m.get("arousal", 0.5) for m in memories if "arousal" in m]
        
        if not valences:
            return {"avg_valence": 0, "avg_arousal": 0, "distribution": {}}
        
        states = {}
        for m in memories:
            if "valence" in m and "arousal" in m:
                state = self._determine_state(m["valence"], m["arousal"])
                states[state.value] = states.get(state.value, 0) + 1
        
        total = len(memories)
        distribution = {k: v/total for k, v in states.items()}
        
        return {
            "avg_valence": sum(valences) / len(valences),
            "avg_arousal": sum(arousals) / len(arousals),
            "distribution": distribution,
            "stability": 1.0 - (max(valences) - min(valences)) if valences else 0.5
        }
    
    def to_dict(self) -> Dict:
        """Export configuration"""
        return {
            "config": self.config,
            "emotion_decay_rates": {k.value: v for k, v in self.emotion_decay_rates.items()},
            "circadian_factors": self.circadian_factors,
            "consolidation_window_hours": self.consolidation_window
        }


# ============================================================================
# ADAPTIVE DECAY - Usage-based importance tracking
# ============================================================================

class AdaptiveDecay:
    """
    Adaptive decay that learns from memory access patterns
    """
    
    def __init__(self, store=None):
        self.store = store
        self.access_tracking = {}
        self.importance_cache = {}
        
        self.default_halflives = {
            "working": 1800,
            "episodic": 14400,
            "semantic": 86400,
            "emotional": 7200,
            "procedural": 259200,
        }
        
        logger.info("✅ AdaptiveDecay initialized")
    
    def track_access(self, memory_id: str, memory_type: str = "general"):
        """Track when a memory is accessed"""
        now = datetime.now().isoformat()
        
        if memory_id not in self.access_tracking:
            self.access_tracking[memory_id] = {
                "access_count": 0,
                "first_access": now,
                "last_access": now,
                "type": memory_type,
                "access_times": []
            }
        
        track = self.access_tracking[memory_id]
        track["access_count"] += 1
        track["last_access"] = now
        track["access_times"].append(now)
        
        if len(track["access_times"]) > 100:
            track["access_times"] = track["access_times"][-100:]
    
    def get_adaptive_importance(self, memory_id: str, base_importance: float = 1.0) -> float:
        """Calculate adaptive importance based on access patterns"""
        if memory_id not in self.access_tracking:
            return base_importance
        
        track = self.access_tracking[memory_id]
        access_count = track["access_count"]
        
        frequency_boost = math.log(access_count + 1) * 0.1
        
        try:
            last_access = datetime.fromisoformat(track["last_access"])
            hours_since = (datetime.now() - last_access).total_seconds() / 3600
            recency_boost = math.exp(-hours_since / 48) * 0.3
        except:
            recency_boost = 0
        
        if len(track["access_times"]) > 2:
            try:
                times = [datetime.fromisoformat(t) for t in track["access_times"][-10:]]
                if len(times) > 2:
                    intervals = [(times[i+1] - times[i]).total_seconds() 
                               for i in range(len(times)-1)]
                    avg_interval = sum(intervals) / len(intervals)
                    variance = sum((i - avg_interval)**2 for i in intervals) / len(intervals)
                    consistency = 1.0 - min(1.0, variance / (avg_interval**2))
                    consistency_boost = consistency * 0.2
                else:
                    consistency_boost = 0
            except:
                consistency_boost = 0
        else:
            consistency_boost = 0
        
        final_importance = base_importance + frequency_boost + recency_boost + consistency_boost
        return min(5.0, final_importance)
    
    def get_halflife_for_memory(self, memory_id: str, memory_type: str) -> float:
        """Get custom half-life based on access patterns"""
        base = self.default_halflives.get(memory_type, 7200)
        
        if memory_id not in self.access_tracking:
            return base
        
        track = self.access_tracking[memory_id]
        access_boost = min(track["access_count"] * 0.1, 3.0)
        
        return base * (1 + access_boost * 0.5)
