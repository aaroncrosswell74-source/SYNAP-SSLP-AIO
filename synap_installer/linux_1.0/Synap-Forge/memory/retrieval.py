"""
SHARP MEMORY RETRIEVAL - Multi-layer, context-aware, emotionally intelligent
=======================================================================
Uses: Redis (working), Chroma (semantic), JSON (archival)
Integrates: emotional_decay, decay, cognitive arbitration
"""

import json
import logging
import math
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np

logger = logging.getLogger(__name__)

# Import from local files (same directory)
from .decay import DecayFunction, PresetDecay
from .emotional_decay import EmotionalDecay, SharpEmotionalDecay, AdaptiveDecay
from .indexing import MemoryIndexer


@dataclass
class MemoryFragment:
    """Enhanced memory with scoring and metadata"""
    content: str
    source: str  # 'redis', 'chroma', 'json', 'core'
    timestamp: str
    score: float = 0.0
    importance: float = 1.0
    emotional_valence: Optional[float] = None
    emotional_arousal: Optional[float] = None
    context_type: str = "general"  # 'conversation', 'fact', 'emotion', 'instruction'
    tags: List[str] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None
    access_count: int = 0
    last_accessed: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
            "score": self.score,
            "importance": self.importance,
            "emotional_valence": self.emotional_valence,
            "emotional_arousal": self.emotional_arousal,
            "context_type": self.context_type,
            "tags": self.tags,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed
        }


class SharpMemoryRetrieval:
    """
    The SHARP memory retrieval system.
    
    SHARP = Semantic, Hierarchical, Adaptive, Recursive, Predictive
    """
    
    def __init__(self, store=None, config: Optional[Dict] = None):
        self.store = store
        self.config = config or self._default_config()
        
        # Initialize decay functions
        self.working_decay = PresetDecay.working_memory()
        self.emotional_decay = PresetDecay.emotional_memory()
        self.semantic_decay = PresetDecay.semantic_memory()
        self.episodic_decay = PresetDecay.episodic_memory()
        
        # Cache for performance
        self._cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 60  # seconds
        
        # Pattern matchers
        self._patterns = self._compile_patterns()
        
        logger.info("✅ SharpMemoryRetrieval initialized")
    
    def _default_config(self) -> Dict:
        return {
            "max_results": 15,
            "semantic_threshold": 0.65,
            "importance_decay_rate": 0.95,
            "emotional_weight": 0.25,
            "recency_weight": 0.35,
            "relevance_weight": 0.40,
            "context_window_minutes": 30,
            "importance_boost_access": 0.1,
        }
    
    def _compile_patterns(self) -> Dict:
        """Compile regex patterns for context detection"""
        return {
            "question": re.compile(r'^(what|why|how|when|where|who|which|does|is|are|can|could|would|will|should|did|do|has|have)\b', re.I),
            "instruction": re.compile(r'\b(please|kindly|remember|note|important|critical|must|need|should|required)\b', re.I),
            "emotion": re.compile(r'\b(sad|happy|angry|excited|worried|anxious|calm|frustrated|grateful|love|hate|fear|joy|surprise|disgust)\b', re.I),
            "factual": re.compile(r'\b(is|are|was|were|has|have|known|defined|called|refers|consists|contains|includes)\b', re.I),
            "time_reference": re.compile(r'\b(today|yesterday|tomorrow|now|then|earlier|later|recently|before|after|when|during|while)\b', re.I),
        }
    
    def search(self, query: str, user_id: str = "default", 
               limit: int = 5, context_window: int = 30) -> List[MemoryFragment]:
        """
        SHARP search - multi-layer memory retrieval
        """
        if not query or not query.strip():
            return []
        
        query_type = self._detect_query_type(query)
        fragments = []
        
        # LAYER 1: Working Memory (Redis)
        fragments.extend(self._retrieve_working_memory(query, user_id, limit))
        
        # LAYER 2: Semantic Memory (Chroma)
        fragments.extend(self._retrieve_semantic_memory(query, limit))
        
        # LAYER 3: Episodic Memory (JSON)
        fragments.extend(self._retrieve_episodic_memory(query, limit))
        
        # LAYER 4: Emotional Memory
        fragments.extend(self._retrieve_emotional_memory(query, limit))
        
        # LAYER 5: Core Memory
        fragments.extend(self._retrieve_core_memory(query))
        
        # Score and rank
        ranked = self._score_and_rank(fragments, query, query_type)
        
        # Apply context window
        filtered = self._apply_context_window(ranked, context_window)
        
        return filtered[:limit]
    
    def _detect_query_type(self, query: str) -> str:
        """Detect what kind of query this is"""
        query_lower = query.lower()
        if self._patterns["question"].search(query_lower):
            return "question"
        elif self._patterns["instruction"].search(query_lower):
            return "instruction"
        elif self._patterns["emotion"].search(query_lower):
            return "emotional"
        elif self._patterns["factual"].search(query_lower):
            return "factual"
        else:
            return "general"
    
    def _retrieve_working_memory(self, query: str, user_id: str, limit: int) -> List[MemoryFragment]:
        """Retrieve from Redis working memory"""
        fragments = []
        try:
            if not self.store or not hasattr(self.store, 'redis') or not self.store.redis:
                return fragments
            
            key = f"chat:{user_id}"
            history = self.store.redis.lrange(key, -50, -1)
            
            for item in history:
                try:
                    msg = json.loads(item)
                    content = msg.get("content", "")
                    if self._text_relevance(query, content) > 0.3:
                        fragments.append(MemoryFragment(
                            content=content,
                            source="redis",
                            timestamp=msg.get("timestamp", datetime.now().isoformat()),
                            score=self._text_relevance(query, content),
                            context_type="conversation",
                            tags=["recent", "conversation"]
                        ))
                except:
                    pass
        except Exception as e:
            logger.debug(f"Working memory retrieval error: {e}")
        return fragments
    
    def _retrieve_semantic_memory(self, query: str, limit: int) -> List[MemoryFragment]:
        """Retrieve from Chroma vector database"""
        fragments = []
        try:
            if not self.store or not hasattr(self.store, 'collection') or not self.store.collection:
                return fragments
            
            results = self.store.collection.get(limit=100)
            if results and 'documents' in results and 'metadatas' in results:
                for i, doc in enumerate(results['documents']):
                    if not doc:
                        continue
                    similarity = self._semantic_similarity(query, doc)
                    if similarity > self.config["semantic_threshold"]:
                        metadata = results['metadatas'][i] if i < len(results['metadatas']) else {}
                        fragments.append(MemoryFragment(
                            content=doc,
                            source="chroma",
                            timestamp=metadata.get('timestamp', datetime.now().isoformat()),
                            score=similarity,
                            context_type="semantic",
                            tags=["vector", "semantic"]
                        ))
        except Exception as e:
            logger.debug(f"Semantic memory retrieval error: {e}")
        return fragments
    
    def _retrieve_episodic_memory(self, query: str, limit: int) -> List[MemoryFragment]:
        """Retrieve from JSON archival storage"""
        fragments = []
        try:
            if not self.store or not hasattr(self.store, 'central_memory'):
                return fragments
            
            interactions_dir = self.store.central_memory / "interactions"
            if not interactions_dir.exists():
                return fragments
            
            files = list(interactions_dir.glob("*.json"))[-30:]
            for file_path in files:
                try:
                    with open(file_path, 'r') as f:
                        mem = json.load(f)
                        content = mem.get("content", "")
                        if not content:
                            continue
                        relevance = self._text_relevance(query, content)
                        if relevance > 0.2:
                            fragments.append(MemoryFragment(
                                content=content,
                                source="json",
                                timestamp=mem.get("timestamp", datetime.now().isoformat()),
                                score=relevance,
                                context_type=mem.get("type", "episodic"),
                                tags=["archival", "historical"]
                            ))
                except:
                    pass
        except Exception as e:
            logger.debug(f"Episodic memory retrieval error: {e}")
        return fragments
    
    def _retrieve_emotional_memory(self, query: str, limit: int) -> List[MemoryFragment]:
        """Retrieve emotionally relevant memories"""
        fragments = []
        query_emotions = self._extract_emotions(query)
        if not query_emotions:
            return fragments
        
        try:
            if self.store and hasattr(self.store, 'get_recent'):
                recent = self.store.get_recent(limit=50)
                for mem in recent:
                    content = mem.get("response_preview", mem.get("user_input_preview", ""))
                    if not content:
                        continue
                    mem_emotions = self._extract_emotions(content)
                    overlap = len(set(query_emotions) & set(mem_emotions))
                    if overlap > 0:
                        fragments.append(MemoryFragment(
                            content=content,
                            source="redis",
                            timestamp=mem.get("timestamp", datetime.now().isoformat()),
                            score=0.6 + (overlap * 0.1),
                            context_type="emotional",
                            tags=["emotional", *query_emotions[:2]]
                        ))
        except Exception as e:
            logger.debug(f"Emotional memory retrieval error: {e}")
        return fragments
    
    def _retrieve_core_memory(self, query: str) -> List[MemoryFragment]:
        """Retrieve from core identity memory"""
        fragments = []
        try:
            if self.store and hasattr(self.store, 'core_memory'):
                core = self.store.core_memory
                identity = core.get("identity", "")
                version = core.get("version", "")
                if identity and any(word in query.lower() for word in ["who", "what", "identity", "name", "version"]):
                    fragments.append(MemoryFragment(
                        content=f"Identity: {identity} (version {version})",
                        source="core",
                        timestamp=datetime.now().isoformat(),
                        score=0.9,
                        context_type="identity",
                        tags=["core", "identity", "permanent"]
                    ))
        except Exception as e:
            logger.debug(f"Core memory retrieval error: {e}")
        return fragments
    
    def _score_and_rank(self, fragments: List[MemoryFragment], query: str, 
                        query_type: str) -> List[MemoryFragment]:
        """Score and rank fragments using multi-factor scoring"""
        now = datetime.now()
        for fragment in fragments:
            try:
                mem_time = datetime.fromisoformat(fragment.timestamp)
                age_seconds = (now - mem_time).total_seconds()
            except:
                age_seconds = 0
            
            recency_score = self.working_decay.calculate_weight(age_seconds)
            relevance_score = fragment.score
            
            importance_score = fragment.importance * (1 + (fragment.access_count * 0.05))
            context_match = self._context_match(query_type, fragment.context_type)
            
            emotional_score = 1.0
            if fragment.emotional_valence is not None:
                emotional_score = 0.5 + (abs(fragment.emotional_valence) * 0.5)
            
            tag_score = 1.0
            if fragment.tags:
                query_words = set(query.lower().split())
                tag_matches = sum(1 for tag in fragment.tags if tag in query_words)
                tag_score = 1.0 + (tag_matches * 0.1)
            
            final_score = (
                relevance_score * self.config["relevance_weight"] +
                recency_score * self.config["recency_weight"] +
                emotional_score * self.config["emotional_weight"] +
                (context_match * 0.1) +
                (importance_score * 0.05) +
                (tag_score * 0.05)
            )
            fragment.score = min(1.0, final_score)
        
        return sorted(fragments, key=lambda x: x.score, reverse=True)
    
    def _context_match(self, query_type: str, memory_type: str) -> float:
        matches = {
            ("question", "conversation"): 0.8,
            ("question", "factual"): 0.9,
            ("instruction", "instruction"): 0.9,
            ("emotional", "emotional"): 1.0,
            ("factual", "semantic"): 0.8,
            ("factual", "conversation"): 0.6,
        }
        return matches.get((query_type, memory_type), 0.5)
    
    def _apply_context_window(self, fragments: List[MemoryFragment], 
                             minutes: int) -> List[MemoryFragment]:
        if minutes <= 0:
            return fragments
        now = datetime.now()
        cutoff = now - timedelta(minutes=minutes)
        filtered = []
        for fragment in fragments:
            try:
                mem_time = datetime.fromisoformat(fragment.timestamp)
                if mem_time >= cutoff or fragment.score > 0.8 or fragment.source == "core":
                    filtered.append(fragment)
            except:
                filtered.append(fragment)
        return filtered
    
    def _text_relevance(self, query: str, text: str) -> float:
        if not query or not text:
            return 0.0
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        if not query_words:
            return 0.0
        intersection = query_words & text_words
        union = query_words | text_words
        if not union:
            return 0.0
        return len(intersection) / len(union)
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        jaccard = len(words1 & words2) / len(words1 | words2) if (words1 | words2) else 0.0
        
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "to", "for", "of", 
                     "and", "or", "but", "in", "on", "at", "with", "without"}
        common_words = words1 & words2
        weighted_overlap = sum(1 for w in common_words if w not in stop_words)
        weighted_total = sum(1 for w in (words1 | words2) if w not in stop_words)
        weighted_jaccard = weighted_overlap / weighted_total if weighted_total > 0 else 0.0
        
        def get_ngrams(text, n=2):
            words = text.lower().split()
            return set(' '.join(words[i:i+n]) for i in range(len(words)-n+1))
        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)
        ngram_jaccard = len(ngrams1 & ngrams2) / len(ngrams1 | ngrams2) if (ngrams1 | ngrams2) else 0.0
        
        return (jaccard * 0.3) + (weighted_jaccard * 0.4) + (ngram_jaccard * 0.3)
    
    def _extract_emotions(self, text: str) -> List[str]:
        emotion_words = {
            'happy': ['happy', 'joy', 'glad', 'delighted', 'pleased', 'cheerful'],
            'sad': ['sad', 'depressed', 'gloomy', 'miserable', 'heartbroken'],
            'angry': ['angry', 'mad', 'furious', 'irritated', 'annoyed'],
            'anxious': ['anxious', 'worried', 'nervous', 'stressed', 'uneasy'],
            'calm': ['calm', 'peaceful', 'relaxed', 'tranquil', 'serene'],
            'excited': ['excited', 'thrilled', 'eager', 'enthusiastic'],
            'fearful': ['afraid', 'scared', 'terrified', 'frightened'],
            'grateful': ['grateful', 'thankful', 'appreciative'],
            'love': ['love', 'adore', 'cherish', 'care'],
            'hate': ['hate', 'dislike', 'despise', 'loathe']
        }
        text_lower = text.lower()
        found = []
        for emotion, words in emotion_words.items():
            if any(word in text_lower for word in words):
                found.append(emotion)
        return found
    
    def format_context(self, memories: List[MemoryFragment], max_chars: int = 2000) -> str:
        """Format memories into context string with source tagging"""
        if not memories:
            return ""
        
        lines = []
        total_chars = 0
        seen_content = set()
        
        for i, mem in enumerate(memories, 1):
            content = mem.content
            if not content:
                continue
            content_hash = content[:100]
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            source_emoji = {
                'redis': '💭',
                'chroma': '🧠',
                'json': '📖',
                'core': '⚡'
            }.get(mem.source, '📌')
            
            score_emoji = '🔴' if mem.score < 0.4 else '🟡' if mem.score < 0.7 else '🟢'
            entry = f"{source_emoji} {score_emoji} Memory #{i}: {content}"
            
            if mem.tags:
                entry += f" [{', '.join(mem.tags[:3])}]"
            if mem.context_type != "general":
                entry += f" ({mem.context_type})"
            
            if len(entry) > total_chars + 500:
                entry = entry[:497] + "..."
            
            lines.append(entry)
            total_chars += len(entry)
            if total_chars > max_chars:
                break
        
        if not lines:
            return ""
        
        return (
            "[SHARP MEMORY CONTEXT]\n"
            "─────────────────────\n"
            + "\n".join(lines) +
            "\n─────────────────────"
        )
    
    def get_memory_stats(self) -> Dict[str, Any]:
        stats = {
            "total_fragments": 0,
            "by_source": {},
            "by_context_type": {},
            "average_score": 0.0,
            "decay_info": {
                "working_half_life": self.working_decay.half_life,
                "emotional_half_life": self.emotional_decay.half_life,
                "semantic_half_life": self.semantic_decay.half_life
            }
        }
        if self.store:
            if hasattr(self.store, 'redis') and self.store.redis:
                try:
                    stats["redis_keys"] = self.store.redis.dbsize()
                    stats["total_fragments"] += stats["redis_keys"]
                    stats["by_source"]["redis"] = stats["redis_keys"]
                except:
                    pass
            if hasattr(self.store, 'collection') and self.store.collection:
                try:
                    stats["chroma_entries"] = self.store.collection.count()
                    stats["total_fragments"] += stats["chroma_entries"]
                    stats["by_source"]["chroma"] = stats["chroma_entries"]
                except:
                    pass
            if hasattr(self.store, 'central_memory'):
                interactions_dir = self.store.central_memory / "interactions"
                if interactions_dir.exists():
                    json_count = len(list(interactions_dir.glob("*.json")))
                    stats["json_files"] = json_count
                    stats["by_source"]["json"] = json_count
                    stats["total_fragments"] += json_count
        return stats

# ============================================================================
# ENHANCED FLOW AWARENESS - Added by Sharp Upgrade
# ============================================================================

    def search_with_flow(self, query: str, user_id: str = "default", 
                          limit: int = 5, context_window: int = 30):
        """Search with conversational flow awareness"""
        if not query or not query.strip():
            return []
        
        # Get current turn context
        current_turn = self._get_current_turn(user_id)
        semantic_matches = self.search(query, user_id, limit * 2, context_window)
        flow_ranked = self._rerank_with_flow(semantic_matches, current_turn, query)
        temporal_boosted = self._boost_temporal_proximity(flow_ranked, current_turn)
        
        return temporal_boosted[:limit]
    
    def _get_current_turn(self, user_id: str):
        """Get current conversational turn"""
        try:
            if self.store and hasattr(self.store, 'redis') and self.store.redis:
                key = f"chat:{user_id}"
                history = self.store.redis.lrange(key, -5, -1)
                turns = []
                for item in history:
                    try:
                        msg = json.loads(item)
                        turns.append({
                            "role": msg.get("role", ""),
                            "content": msg.get("content", ""),
                            "timestamp": msg.get("timestamp", "")
                        })
                    except:
                        pass
                for turn in reversed(turns):
                    if turn['role'] == 'user':
                        return {
                            "last_user_turn": turn,
                            "recent_turns": turns[-3:],
                            "turn_count": len(turns)
                        }
                return {"last_user_turn": None, "recent_turns": turns, "turn_count": len(turns)}
        except:
            pass
        return {"last_user_turn": None, "recent_turns": [], "turn_count": 0}
    
    def _rerank_with_flow(self, fragments, current_turn, query):
        """Rerank memories based on conversational flow"""
        if not fragments:
            return fragments
        
        last_user = current_turn.get('last_user_turn', {})
        last_user_content = last_user.get('content', '')
        recent_turns = current_turn.get('recent_turns', [])
        
        recent_themes = []
        for turn in recent_turns[-3:]:
            content = turn.get('content', '')
            if content:
                recent_themes.extend(content.lower().split()[:10])
        
        for fragment in fragments:
            # Temporal appropriateness
            try:
                mem_time = datetime.fromisoformat(fragment.timestamp)
                turn_age = current_turn.get('turn_count', 0) - self._estimate_turn_age(fragment)
                if turn_age > 10:
                    temporal_penalty = max(0, 1 - (turn_age - 10) / 20)
                    fragment.score *= temporal_penalty
            except:
                pass
            
            # Flow coherence
            if last_user_content and fragment.content:
                flow_score = self._flow_coherence(fragment.content, last_user_content, recent_themes)
                fragment.score = (fragment.score * 0.7) + (flow_score * 0.3)
        
        return sorted(fragments, key=lambda x: x.score, reverse=True)
    
    def _flow_coherence(self, memory_content, last_user, recent_themes):
        """Calculate flow coherence score"""
        if not last_user:
            return 0.5
        
        memory_words = set(memory_content.lower().split())
        last_words = set(last_user.lower().split())
        overlap = len(memory_words & last_words) / len(last_words) if last_words else 0
        
        theme_overlap = 0
        if recent_themes:
            theme_words = set(recent_themes)
            theme_overlap = len(memory_words & theme_words) / len(theme_words) if theme_words else 0
        
        return min(1.0, (overlap * 0.7) + (theme_overlap * 0.3))
    
    def _estimate_turn_age(self, fragment):
        """Estimate turns ago"""
        try:
            mem_time = datetime.fromisoformat(fragment.timestamp)
            now = datetime.now()
            seconds_ago = (now - mem_time).total_seconds()
            return int(seconds_ago / 30)
        except:
            return 0
    
    def _boost_temporal_proximity(self, fragments, current_turn):
        """Boost recent memories"""
        if not fragments:
            return fragments
        
        for fragment in fragments:
            turn_age = self._estimate_turn_age(fragment)
            if turn_age <= 5:
                boost = 1.0 - (turn_age / 6)
                fragment.score += boost * 0.2
            elif turn_age > 20 and fragment.score < 0.7:
                fragment.score *= 0.5
        
        return sorted(fragments, key=lambda x: x.score, reverse=True)
    

# Patch search method - outside class
_original_search = SharpMemoryRetrieval.search

def _patched_search(self, query, user_id="default", limit=5, context_window=30):
    """Patched search method using flow by default."""
    return self.search_with_flow(query, user_id, limit, context_window)

SharpMemoryRetrieval.search = _patched_search
