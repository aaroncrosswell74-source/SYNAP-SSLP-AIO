"""
Memory SHARP Integration - Glue all components together
========================================================
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# Import from the actual file names
from .retrieval import SharpMemoryRetrieval, MemoryFragment
from .emotional_decay import SharpEmotionalDecay, AdaptiveDecay

logger = logging.getLogger(__name__)


class SharpMemorySystem:
    """
    Complete Sharp Memory System
    
    Integrates:
    - SharpMemoryRetrieval (search, scoring, ranking)
    - SharpEmotionalDecay (emotional decay management)
    - AdaptiveDecay (usage-based importance)
    - MemoryStore (Redis + Chroma + JSON)
    """
    
    def __init__(self, store=None):
        self.store = store
        
        # Initialize components
        self.retrieval = SharpMemoryRetrieval(store=store)
        self.emotional_decay = SharpEmotionalDecay()
        self.adaptive_decay = AdaptiveDecay(store=store)
        
        # Stats
        self.stats = {
            "total_searches": 0,
            "total_retrievals": 0,
            "avg_results": 0,
            "hit_rate": 0,
            "recall_cache": {}
        }
        
        logger.info("✅ SharpMemorySystem ready")
    
    def recall(self, query: str, user_id: str = "default", 
              limit: int = 5, include_emotions: bool = True) -> Dict[str, Any]:
        """
        Main recall function - get memories and context
        """
        self.stats["total_searches"] += 1
        
        # 1. Retrieve memories
        fragments = self.retrieval.search(query, user_id, limit * 2)
        
        # 2. Apply emotional decay weighting
        if include_emotions and fragments:
            now = datetime.now()
            for fragment in fragments:
                try:
                    timestamp = datetime.fromisoformat(fragment.timestamp)
                    decay_info = self.emotional_decay.calculate_decay(
                        valence=fragment.emotional_valence or 0,
                        arousal=fragment.emotional_arousal or 0.5,
                        timestamp=timestamp,
                        now=now
                    )
                    fragment.score *= decay_info["decay_weight"]
                    fragment.importance = self.adaptive_decay.get_adaptive_importance(
                        fragment.content[:100],
                        base_importance=1.0
                    )
                except Exception as e:
                    logger.debug(f"Emotional decay error: {e}")
        
        # 3. Limit results
        top_fragments = fragments[:limit]
        
        # 4. Track accesses
        for fragment in top_fragments:
            self.adaptive_decay.track_access(
                fragment.content[:100], 
                fragment.context_type
            )
        
        # 5. Format context
        context = self.retrieval.format_context(top_fragments)
        
        # 6. Get emotional profile
        emotion_profile = None
        if include_emotions and fragments:
            emotion_profile = self.emotional_decay.get_emotional_profile(
                [f.to_dict() for f in fragments[:20]]
            )
        
        # 7. Update stats
        self.stats["total_retrievals"] += 1
        self.stats["avg_results"] = (
            (self.stats["avg_results"] * (self.stats["total_retrievals"] - 1) + len(top_fragments))
            / self.stats["total_retrievals"]
        )
        self.stats["hit_rate"] = min(1.0, (self.stats["hit_rate"] * 0.9) + 
                                   (0.1 if len(top_fragments) > 0 else 0))
        
        return {
            "memories": [f.to_dict() for f in top_fragments],
            "context": context,
            "emotions": emotion_profile,
            "metadata": {
                "query_type": self.retrieval._detect_query_type(query),
                "total_candidates": len(fragments),
                "returned": len(top_fragments),
                "timestamp": datetime.now().isoformat(),
                "stats": {
                    "searches": self.stats["total_searches"],
                    "hit_rate": self.stats["hit_rate"],
                    "avg_results": self.stats["avg_results"]
                }
            }
        }
    
    def inject_context(self, query: str, base_prompt: str, user_id: str = "default") -> str:
        """Inject relevant memories into a prompt"""
        recall_result = self.recall(query, user_id, limit=5)
        
        if recall_result["memories"]:
            context = recall_result["context"]
            if "[SHARP MEMORY CONTEXT]" in base_prompt:
                return base_prompt
            else:
                return f"{context}\n\n{base_prompt}"
        
        return base_prompt
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "sharp_retrieval": {
                "config": self.retrieval.config,
                "patterns": len(self.retrieval._patterns) if hasattr(self.retrieval, '_patterns') else 0
            },
            "emotional_decay": self.emotional_decay.to_dict() if hasattr(self.emotional_decay, 'to_dict') else {},
            "adaptive_decay": {
                "tracked_memories": len(self.adaptive_decay.access_tracking),
                "default_halflives": self.adaptive_decay.default_halflives
            },
            "stats": self.stats,
            "memory_stats": self.retrieval.get_memory_stats()
        }

# ============================================================================
# TURN TRACKING - Added by Sharp Upgrade
# ============================================================================

class TurnAwareMemorySystem(SharpMemorySystem):
    """Memory system with conversational turn awareness"""
    
    def __init__(self, store=None):
        super().__init__(store)
        self.turn_history = []
        self.current_topic = None
        self.turn_count = 0
    
    def recall_with_turns(self, query: str, user_id: str = "default", 
                         limit: int = 5, include_emotions: bool = True):
        """Recall with turn awareness"""
        # Use the flow-aware search
        fragments = self.retrieval.search_with_flow(query, user_id, limit * 2)
        
        # Rest of recall logic...
        if include_emotions and fragments:
            now = datetime.now()
            for fragment in fragments:
                try:
                    timestamp = datetime.fromisoformat(fragment.timestamp)
                    decay_info = self.emotional_decay.calculate_decay(
                        valence=fragment.emotional_valence or 0,
                        arousal=fragment.emotional_arousal or 0.5,
                        timestamp=timestamp,
                        now=now
                    )
                    fragment.score *= decay_info["decay_weight"]
                    fragment.importance = self.adaptive_decay.get_adaptive_importance(
                        fragment.content[:100],
                        base_importance=1.0
                    )
                except Exception as e:
                    logger.debug(f"Emotional decay error: {e}")
        
        top_fragments = fragments[:limit]
        
        for fragment in top_fragments:
            self.adaptive_decay.track_access(
                fragment.content[:100], 
                fragment.context_type
            )
        
        context = self.retrieval.format_context(top_fragments)
        
        emotion_profile = None
        if include_emotions and fragments:
            emotion_profile = self.emotional_decay.get_emotional_profile(
                [f.to_dict() for f in fragments[:20]]
            )
        
        self.stats["total_retrievals"] += 1
        self.stats["avg_results"] = (
            (self.stats["avg_results"] * (self.stats["total_retrievals"] - 1) + len(top_fragments))
            / self.stats["total_retrievals"]
        )
        self.stats["hit_rate"] = min(1.0, (self.stats["hit_rate"] * 0.9) + 
                                   (0.1 if len(top_fragments) > 0 else 0))
        
        return {
            "memories": [f.to_dict() for f in top_fragments],
            "context": context,
            "emotions": emotion_profile,
            "metadata": {
                "query_type": self.retrieval._detect_query_type(query),
                "total_candidates": len(fragments),
                "returned": len(top_fragments),
                "turn_count": self.turn_count,
                "timestamp": datetime.now().isoformat(),
                "stats": {
                    "searches": self.stats["total_searches"],
                    "hit_rate": self.stats["hit_rate"],
                    "avg_results": self.stats["avg_results"]
                }
            }
        }
    
    def record_turn(self, user_input: str, response: str):
        """Record a conversational turn"""
        self.turn_count += 1
        self.turn_history.append({
            "turn": self.turn_count,
            "user": user_input,
            "assistant": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update current topic
        words = user_input.lower().split()
        if words:
            self.current_topic = words[0]  # Simple topic extraction
    
    def get_recent_turns(self, limit: int = 3) -> str:
        """Get recent turns as context"""
        if not self.turn_history:
            return ""
        
        recent = self.turn_history[-limit:]
        lines = []
        for turn in recent:
            lines.append(f"User: {turn['user'][:100]}")
            lines.append(f"Assistant: {turn['assistant'][:100]}")
        return "\n".join(lines)
