"""
Episodic Buffer - Time‑ordered event storage
=============================================
Stores episodes (user turns, system turns, internal events) with:
- timestamp
- episode type (user, assistant, internal)
- emotional valence
- importance
- linkage to semantic memories (via IDs)
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import deque
from ...loop.decay import DecayFunction   # fixed path

logger = logging.getLogger(__name__)


class EpisodicBuffer:
    """
    A sliding buffer of recent episodes with optional persistence.
    Episodes can be later consolidated into semantic memory.
    """

    def __init__(self, max_size: int = 100, half_life: float = 3600.0):
        self.buffer: deque = deque(maxlen=max_size)
        self.decay = DecayFunction(half_life)
        self.current_session_id = str(uuid.uuid4())

    def add_episode(
        self,
        episode_type: str,   # "user", "assistant", "internal"
        content: str,
        emotional_valence: float = 0.0,   # -1 (negative) to +1 (positive)
        importance: float = 0.5,
        linked_memory_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a new episode to the buffer.
        Returns episode ID.
        """
        episode_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        episode = {
            "id": episode_id,
            "session_id": self.current_session_id,
            "timestamp": timestamp,
            "type": episode_type,
            "content": content,
            "emotional_valence": emotional_valence,
            "importance": importance,
            "linked_memory_ids": linked_memory_ids or [],
            "metadata": metadata or {}
        }
        self.buffer.append(episode)
        logger.debug(f"Added episode {episode_id} ({episode_type})")
        return episode_id

    def get_recent_episodes(self, limit: int = 10, min_importance: float = 0.0) -> List[Dict[str, Any]]:
        """Return the most recent episodes, filtered by importance."""
        filtered = [e for e in self.buffer if e["importance"] >= min_importance]
        return list(reversed(filtered[-limit:]))

    def get_episodes_since(self, timestamp: str, min_importance: float = 0.0) -> List[Dict[str, Any]]:
        """Return episodes after the given ISO timestamp."""
        try:
            since_dt = datetime.fromisoformat(timestamp)
        except Exception:
            return []
        result = []
        for e in self.buffer:
            try:
                dt = datetime.fromisoformat(e["timestamp"])
                if dt > since_dt and e["importance"] >= min_importance:
                    result.append(e)
            except Exception:
                continue
        return result

    def compute_recency_weight(self, episode: Dict[str, Any], current_time: Optional[datetime] = None) -> float:
        """Compute decay weight based on episode age."""
        if current_time is None:
            current_time = datetime.now()
        try:
            dt = datetime.fromisoformat(episode["timestamp"])
            age = (current_time - dt).total_seconds()
            return self.decay.calculate_weight(age)
        except Exception:
            return 0.0

    def clear_session(self):
        """Start a new session (clears buffer or archives)."""
        self.buffer.clear()
        self.current_session_id = str(uuid.uuid4())
        logger.info("Episodic buffer cleared for new session")

    def get_statistics(self) -> Dict[str, Any]:
        """Return basic stats about the buffer."""
        types = {}
        for e in self.buffer:
            t = e["type"]
            types[t] = types.get(t, 0) + 1
        return {
            "total_episodes": len(self.buffer),
            "session_id": self.current_session_id,
            "by_type": types,
            "avg_importance": sum(e["importance"] for e in self.buffer) / max(len(self.buffer), 1),
            "avg_valence": sum(e["emotional_valence"] for e in self.buffer) / max(len(self.buffer), 1)
        }