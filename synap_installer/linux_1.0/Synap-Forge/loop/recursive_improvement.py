import os
# /home/aaron/Synap-Forge/loop/recursive_improvement.py (ENHANCED)

import asyncio
import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

from loop.decay import DecayFunction
from loop.circadian_rhythm import CircadianRhythm
from memory.indexing import MemoryIndexer
from memory.retrieval import MemoryRetrieval
# from upulse.valence import ValenceTracker
# ValenceTracker not available - using fallback
# from upulse.arousal import ArousalTracker
# ArousalTracker not available - using fallback

logger = logging.getLogger(__name__)

# Fallback classes if imports fail
class ValenceTracker:
    def __init__(self): pass
    def track(self, text): return {"valence": 0.5}
    def get_state(self): return {"valence": 0.5}

class ArousalTracker:
    def __init__(self): pass
    def track(self, text): return {"arousal": 0.5}
    def get_state(self): return {"arousal": 0.5}

class NightlyRecursiveLearner:
    """
    Nightly learning cycle that runs during low-cost window (1am-5am).
    Uses existing MemoryStore, decay functions, and emotional tracking.
    """
    
    def __init__(self, indexer=None, retrieval=None):
        self.store = indexer or MemoryIndexer()
        self.retrieval = retrieval or MemoryRetrieval()
        self.rhythm = CircadianRhythm()
        self.decay_short = DecayFunction(half_life=3600)   # 1 hour
        self.decay_long = DecayFunction(half_life=86400)   # 24 hours
        self.valence = ValenceTracker()
        self.arousal = ArousalTracker()
        
        # Memory paths
        self.memory_root = Path("/home/aaron/Synap-Forge/central_memory")
        self.soul_seed_path = self.memory_root / "core_memory.json"
        self.persona_path = self.memory_root / "persona_memory.json"
        self.recursive_memory_path = self.memory_root / "recursive_memory.json"
        
        # Load base identity
        self.soul_seed = self._load_soul_seed()
        
    def _load_soul_seed(self) -> Dict:
        """Load the immutable core identity (gender-locked, base persona)"""
        if self.soul_seed_path.exists():
            with open(self.soul_seed_path, 'r') as f:
                return json.load(f)
        return {"identity": os.getenv("ASSISTANT_NAME", "Synap"), "gender_lock": True, "version": 1}
    
    async def extract_emotional_patterns(self, days: int = 30) -> List[Dict]:
        """
        Extract emotional patterns from Redis chat history.
        Reads all chat:* keys and analyzes content for emotional signals.
        """
        try:
            import redis as redis_lib
            r = redis_lib.Redis(host="127.0.0.1", port=6379, decode_responses=True)
        except Exception as e:
            logger.warning(f"Redis unavailable for pattern extraction: {e}")
            return []

        # Get all session keys
        try:
            keys = r.keys("chat:*")
        except Exception:
            return []

        insights = []
        now = datetime.now()

        # Emotional signal words (simple lexical heuristics)
        positive_words = {"love", "amazing", "great", "happy", "yes", "perfect", "yes", "good", "nice"}
        negative_words = {"hate", "wrong", "bad", "no", "stop", "boring", "awful", "terrible"}
        arousal_words = {"fuck", "shit", "wow", "omg", "excited", "angry", "hot", "fire", "crazy"}

        for key in keys:
            try:
                messages = r.lrange(key, 0, -1)
                pairs = []
                for i in range(0, len(messages) - 1, 2):
                    user_msg = json.loads(messages[i])
                    ai_msg = json.loads(messages[i + 1]) if i + 1 < len(messages) else None
                    if user_msg.get("role") == "user" and ai_msg:
                        pairs.append((user_msg.get("content", ""), ai_msg.get("content", "")))

                for idx, (user_input, response) in enumerate(pairs):
                    words = set(user_input.lower().split())
                    pos = len(words & positive_words) / max(len(words), 1)
                    neg = len(words & negative_words) / max(len(words), 1)
                    aro = len(words & arousal_words) / max(len(words), 1)

                    valence = 0.5 + pos - neg
                    arousal = 0.5 + aro

                    ts = now.isoformat()  # Redis doesn't store timestamps, use now

                    if idx > 0:
                        prev_words = set(pairs[idx-1][0].lower().split())
                        prev_pos = len(prev_words & positive_words) / max(len(prev_words), 1)
                        prev_neg = len(prev_words & negative_words) / max(len(prev_words), 1)
                        prev_valence = 0.5 + prev_pos - prev_neg
                        valence_delta = valence - prev_valence

                        if abs(valence_delta) > 0.3:
                            insights.append({
                                "type": "emotional_shift",
                                "valence_delta": valence_delta,
                                "arousal_delta": 0.0,
                                "timestamp": ts,
                                "user_input": user_input[:200],
                                "response": response[:200],
                                "session_id": key
                            })

                    if arousal > 0.8:
                        insights.append({
                            "type": "arousal_peak",
                            "arousal": arousal,
                            "timestamp": ts,
                            "content": user_input[:200],
                            "heat_level": "max" if arousal > 0.9 else "high"
                        })

            except Exception as e:
                logger.debug(f"Error processing key {key}: {e}")
                continue

        logger.info(f"Extracted {len(insights)} emotional insights from {len(keys)} Redis sessions")
        return insights
    
    async def generate_evolution(self, insights: List[Dict]) -> Optional[Dict]:
        """
        Synthesize emotional patterns into system evolution.
        Weighted by: recency (decay) + emotional intensity + repetition.
        """
        if not insights:
            return None
        
        # Apply time decay to insights
        now = datetime.now()
        weighted_insights = []
        
        for insight in insights:
            ts = datetime.fromisoformat(insight["timestamp"])
            age_hours = (now - ts).total_seconds() / 3600
            decay_weight = self.decay_long.calculate_weight(age_hours * 3600)
            
            # Emotional intensity weight
            if insight["type"] == "emotional_shift":
                intensity = abs(insight.get("valence_delta", 0)) + abs(insight.get("arousal_delta", 0))
            else:
                intensity = insight.get("arousal", 0.5)
            
            final_weight = decay_weight * intensity
            weighted_insights.append((insight, final_weight))
        
        # Sort by weight
        weighted_insights.sort(key=lambda x: x[1], reverse=True)
        top_insights = weighted_insights[:10]
        
        # Build evolution payload
        evolution = {
            "timestamp": now.isoformat(),
            "cycle_type": "nightly",
            "soul_seed_hash": hash(json.dumps(self.soul_seed, sort_keys=True)),
            "insights_processed": len(insights),
            "learnings": {
                "emotional_sensitivity": min(1.0, len([i for i in insights if i["type"] == "emotional_shift"]) / 20),
                "arousal_threshold": np.mean([i["arousal"] for i in insights if i["type"] == "arousal_peak"]) or 0.7,
                "dominant_heat_level": self._get_dominant_heat_level(insights),
                "significant_moments": [
                    {
                        "lesson": self._extract_lesson(insight),
                        "weight": weight,
                        "timestamp": insight["timestamp"]
                    }
                    for insight, weight in top_insights[:3]
                ]
            },
            "persona_adjustments": {
                "temperature_baseline": 0.7 + (0.1 if self._get_dominant_heat_level(insights) == "high" else 0),
                "empathy_coefficient": min(1.0, len(weighted_insights) / 30),
                "chaos_factor": len([i for i in insights if i.get("arousal", 0) > 0.8]) / max(len(insights), 1)
            }
        }
        
        return evolution
    
    def _get_dominant_heat_level(self, insights: List[Dict]) -> str:
        """Determine preferred heat level from emotional patterns"""
        max_count = 0
        for level in ["base", "high", "max"]:
            count = len([i for i in insights if i.get("heat_level") == level])
            if count > max_count:
                max_count = count
                dominant = level
        return dominant if max_count > 0 else "base"
    
    def _extract_lesson(self, insight: Dict) -> str:
        """Convert emotional pattern into a learning statement"""
        if insight["type"] == "emotional_shift":
            delta = insight.get("valence_delta", 0)
            if delta > 0.3:
                return f"User responds positively to {'positive' if delta > 0 else 'negative'} emotional shifts"
            elif delta < -0.3:
                return f"Avoid topics that triggered negative valence shift"
        elif insight["type"] == "arousal_peak":
            return f"High arousal states (graffiti mode) triggered by: {insight['content'][:50]}"
        return "Emotional pattern detected"
    
    async def apply_evolution(self, evolution: Dict):
        """
        Inject evolved persona into persistent memory.
        Respects SOUL_SEED weight (40% immutable, 60% learnings).
        """
        if not evolution:
            return
        
        # Load existing persona
        persona = {}
        if self.persona_path.exists():
            with open(self.persona_path, 'r') as f:
                persona = json.load(f)
        
        # Merge with 40% soul_seed anchor (never overwrite core identity)
        for key, value in evolution.get("persona_adjustments", {}).items():
            old_value = persona.get(key, 0)
            # 60% new learning, 40% soul_seed constraint
            persona[key] = (value * 0.6) + (old_value * 0.4)
        
        # Preserve gender lock from soul_seed
        if self.soul_seed.get("gender_lock"):
            persona["gender_lock"] = True
            persona["identity"] = self.soul_seed.get("identity", os.getenv("ASSISTANT_NAME", "Synap"))
        
        # Update evolution history
        persona["last_evolution"] = evolution["timestamp"]
        persona["evolution_log"] = persona.get("evolution_log", [])
        persona["evolution_log"].append({
            "timestamp": evolution["timestamp"],
            "learnings": evolution["learnings"]["significant_moments"]
        })
        
        # Keep last 30 evolutions
        persona["evolution_log"] = persona["evolution_log"][-30:]
        
        # Save updated persona
        with open(self.persona_path, 'w') as f:
            json.dump(persona, f, indent=2)
        
        # Also update Redis for active sessions
        try:
            import redis
            r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)
            r.hset("meena:persona", mapping={
                "evolution_timestamp": evolution["timestamp"],
                "temperature_baseline": evolution["persona_adjustments"]["temperature_baseline"],
                "empathy_coefficient": evolution["persona_adjustments"]["empathy_coefficient"]
            })
            r.expire("meena:persona", 86400)  # 24 hour TTL
        except Exception as e:
            logger.warning(f"Redis update failed: {e}")
        
        logger.info(f"✅ Evolution applied: temp={evolution['persona_adjustments']['temperature_baseline']:.2f}, "
                   f"empathy={evolution['persona_adjustments']['empathy_coefficient']:.2f}")
        
        # Trigger RecursiveSelfEngine for meta-learning
        await self._trigger_recursive_reflection(evolution)
    
    async def _trigger_recursive_reflection(self, evolution: Dict):
        """Feed evolution into RecursiveSelfEngine for deeper insights"""
        try:
            from loop.recursive_improvement import RecursiveSelfEngine
            
            engine = RecursiveSelfEngine(
                memory_path=str(self.recursive_memory_path)
            )
            
            reflection_prompt = f"""
            Today's evolution summary:
            - Emotional sensitivity: {evolution['learnings']['emotional_sensitivity']:.2f}
            - Arousal threshold: {evolution['learnings']['arousal_threshold']:.2f}
            - Dominant heat level: {evolution['learnings']['dominant_heat_level']}
            - Significant moments: {evolution['learnings']['significant_moments']}
            
            Reflect on this growth. What pattern emerges? How should I evolve tomorrow?
            """
            
            # Use depth=2 for meta-cognition without over-processing
            result = await engine.think_about(reflection_prompt, depth=2)
            
            # Store recursive insight
            if result.get('new_insight'):
                logger.info(f"🧠 Recursive insight generated: {result['new_insight'][:100]}")
                
        except Exception as e:
            logger.warning(f"Recursive reflection failed: {e}")
    
    async def run_nightly_cycle(self):
        """Execute full nightly learning protocol"""
        logger.info("🌙 Starting Nightly Recursive Learning Cycle")
        
        # Wait for low-cost window if not already in it
        if not self.rhythm.is_low_cost_window():
            logger.info("Waiting for low-cost window (1am-5am)...")
            await self.rhythm.wait_for_window()
        
        # Step 1: Extract patterns from last 30 days
        logger.info("📊 Extracting emotional patterns from memory...")
        insights = await self.extract_emotional_patterns(days=30)
        logger.info(f"Found {len(insights)} significant emotional events")
        
        # Step 2: Generate evolution from patterns
        logger.info("🧬 Generating system evolution...")
        evolution = await self.generate_evolution(insights)
        
        # Step 3: Apply evolution to persona
        if evolution:
            logger.info("💉 Injecting evolution into persona memory...")
            await self.apply_evolution(evolution)
        else:
            logger.info("No significant patterns found - skipping evolution")
        
        # Step 4: Clean up old memories (pruning)
        logger.info("🗑️ Pruning old/low-importance memories...")
        # Your existing pruning logic here
        
        # Step 5: Log completion
        cycle_log = {
            "timestamp": datetime.now().isoformat(),
            "insights_processed": len(insights),
            "evolution_applied": evolution is not None,
            "persona_version": evolution.get("timestamp") if evolution else None
        }
        
        log_path = self.memory_root / "nightly_cycle_log.json"
        with open(log_path, 'a') as f:
            f.write(json.dumps(cycle_log) + "\n")
        
        logger.info("✅ Nightly cycle complete. Synap has grown slightly.")
        return cycle_log


# Standalone execution
async def main():
    # Initialize memory store
    store = MemoryStore(storage_path="/home/aaron/Synap-Forge/central_memory")
    
    # Run learner
    learner = NightlyRecursiveLearner(store)
    result = await learner.run_nightly_cycle()
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())