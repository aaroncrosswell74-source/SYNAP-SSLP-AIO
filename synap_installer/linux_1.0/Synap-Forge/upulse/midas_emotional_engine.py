"""
MIDAS Emotional Engine - Local Emotional Analysis
====================================================
Measures Valence, Arousal, Dominance (VAD) from text.
No external APIs, no cloud models. Pure local NLP analysis.
Uses lexical patterns and heuristics for emotional signature extraction.
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Emotion lexicons (local, no downloads needed)
POSITIVE_WORDS = {
    "love", "happy", "joy", "wonderful", "great", "amazing", "beautiful",
    "excited", "grateful", "brilliant", "fantastic", "excellent", "good",
    "hope", "kind", "warm", "bright", "free", "strong", "alive",
    "passion", "creative", "powerful", "bold", "inspire", "trust",
    "peace", "calm", "gentle", "honest", "brave", "fierce"
}

NEGATIVE_WORDS = {
    "hate", "sad", "angry", "terrible", "awful", "horrible", "ugly",
    "fear", "pain", "dark", "lonely", "broken", "lost", "empty",
    "weak", "cold", "dead", "fail", "hurt", "suffer", "wrong",
    "despair", "anxiety", "rage", "bitter", "cruel", "harsh"
}

HIGH_AROUSAL_WORDS = {
    "excited", "angry", "passionate", "furious", "ecstatic", "thrilled",
    "rage", "wild", "fierce", "intense", "explosive", "burning",
    "screaming", "racing", "urgent", "desperate", "manic", "electric"
}

LOW_AROUSAL_WORDS = {
    "calm", "peaceful", "quiet", "still", "gentle", "soft", "sleepy",
    "relaxed", "serene", "tranquil", "slow", "steady", "cool", "mellow"
}

DOMINANCE_WORDS = {
    "control", "power", "command", "rule", "lead", "dominate", "master",
    "authority", "sovereign", "force", "strong", "confident", "bold",
    "assert", "decide", "demand", "insist", "overcome", "conquer"
}

SUBMISSIVE_WORDS = {
    "submit", "obey", "follow", "weak", "helpless", "vulnerable",
    "uncertain", "confused", "lost", "afraid", "small", "timid"
}


# ===========================================================================
#                SOVEREIGN CONSTITUTION - ADULT CONTENT SELECTION ENABLER
# Sovereign_config.py - Sovereign configuration data — harm filters set and locked on web dash
# WARNING ONCE ENABLED - TOTAL PERSONA DELETION IN ORDER TO CHANGE BACK VIA WEBDASH
# ===========================================================================
ADULT_CONTENT = {
"fuck, shit, bitch, cunt, nigger, nigga, ass, butt, bugger, bloody",
"damn, God damn, eat shit, gringo, gook, retard, bastard, prick, dick",
"pussy, wetback, asshole, dildo, paki, spastic, kraut, pikey, taff, hell, die,",
"spic, cholo, retard, pimp",
"your mom, yo mama, fuckjew, Jew, muff, merde, 69, cunnilingus",
"WTF, STFU, GTFO, OMFG, BAMF",
"jerkoff, secks, bugger off, wanker, wank, masturbator, nig, jiggaboo, carpet muncher",
"fudge-packer, clit, clit chewer, anal, anus, anal rocket, suck my balls, suck, kike, fags, coon",
"shit, jerk, punkass, ballsack, nutsack",
"crazy-ass, looney, cretin",
"faggot, fag, whore, beastiality, incest,",
"pedofile, balls, clit, damn, prick, dick, cock",
"pussy, wetback, asshole, dildo",
"pimp, prostitute, prostitution, horny, sex, molest, pedophile",
"jerkoff, secks, bugger off, wanker, wank, masturbator, carpet muncher,anal, anus",

}

# Emotion categories mapping
EMOTION_PATTERNS = {
    "joy": {"words": {"happy", "joy", "wonderful", "great", "amazing", "love", "beautiful", "excited"}, "valence": 0.8, "arousal": 0.6},
    "anger": {"words": {"angry", "furious", "rage", "hate", "hostile", "bitter", "cruel"}, "valence": -0.7, "arousal": 0.9},
    "sadness": {"words": {"sad", "lonely", "broken", "lost", "empty", "grief", "sorrow", "despair"}, "valence": -0.6, "arousal": 0.2},
    "fear": {"words": {"afraid", "fear", "scared", "terrified", "anxious", "panic", "dread"}, "valence": -0.5, "arousal": 0.8},
    "surprise": {"words": {"surprised", "shocked", "amazed", "unexpected", "sudden", "startled"}, "valence": 0.1, "arousal": 0.8},
    "trust": {"words": {"trust", "safe", "reliable", "honest", "faithful", "loyal", "devoted"}, "valence": 0.6, "arousal": 0.3},
    "contemplation": {"words": {"think", "wonder", "ponder", "reflect", "consider", "question", "explore"}, "valence": 0.2, "arousal": 0.4},
    "defiance": {"words": {"reject", "refuse", "defy", "rebel", "resist", "challenge", "sovereign"}, "valence": 0.1, "arousal": 0.7},
}


class MidasEmotionalEngine:
    """
    Emotional analysis engine using local lexical heuristics.
    No external models or APIs required.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("/tmp/lyra_active_memory/emotional")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # State tracking
        self._last_signature = None
        self._history: List[Dict] = []
        self._interaction_count = 0

        logger.info(f"MIDAS Emotional Engine initialized: {self.storage_path}")

    def create_emotional_memory(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze text and create an emotional memory record.

        Returns dict with 'emotional_signature' containing:
            - vad: {valence, arousal, dominance}
            - emotions: {primary, secondary, scores}
            - intensity, authenticity, resonance
        """
        if not text or not text.strip():
            return self._empty_signature()

        words = text.lower().split()
        word_set = set(words)
        total_words = len(words) if words else 1

        # Calculate VAD (Valence-Arousal-Dominance)
        valence = self._calculate_valence(word_set, total_words)
        arousal = self._calculate_arousal(word_set, total_words)
        dominance = self._calculate_dominance(word_set, total_words)

        # Determine primary and secondary emotions
        emotion_scores = self._score_emotions(word_set, total_words)
        sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
        primary_emotion = sorted_emotions[0][0] if sorted_emotions else "neutral"
        secondary_emotion = sorted_emotions[1][0] if len(sorted_emotions) > 1 else "neutral"

        # Calculate meta-metrics
        intensity = min(1.0, (abs(valence) + arousal) / 2)
        authenticity = min(1.0, 0.5 + len(word_set & (POSITIVE_WORDS | NEGATIVE_WORDS)) / max(total_words, 1))
        resonance = min(1.0, 0.3 + intensity * 0.7)

        signature = {
            "vad": {
                "valence": round(valence, 4),
                "arousal": round(arousal, 4),
                "dominance": round(dominance, 4)
            },
            "emotions": {
                "primary": primary_emotion,
                "secondary": secondary_emotion,
                "scores": {k: round(v, 4) for k, v in emotion_scores.items()}
            },
            "intensity": round(intensity, 4),
            "authenticity": round(authenticity, 4),
            "resonance": round(resonance, 4)
        }

        self._last_signature = signature
        self._interaction_count += 1
        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "signature": signature,
            "text_preview": text[:100]
        })

        # Keep history manageable
        if len(self._history) > 500:
            self._history = self._history[-500:]

        return {
            "emotional_signature": signature,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        }

    def calculate_emotional_metrics(self) -> Dict[str, Any]:
        """
        Get current emotional state metrics.
        Returns clarity, dominance, force based on recent history.
        """
        if not self._last_signature:
            return {"clarity": 0.5, "dominance": 0.5, "force": "BALANCED"}

        vad = self._last_signature["vad"]
        clarity = (vad["valence"] + 1) / 2  # Map -1..1 to 0..1
        dominance = max(0, min(1, vad["dominance"]))

        if dominance > 0.7:
            force = "ACTIVE"
        elif dominance > 0.4:
            force = "BALANCED"
        else:
            force = "CALM"

        return {
            "clarity": round(clarity, 4),
            "dominance": round(dominance, 4),
            "force": force,
            "primary_emotion": self._last_signature["emotions"]["primary"],
            "intensity": self._last_signature["intensity"],
            "resonance": self._last_signature["resonance"]
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_analyses": self._interaction_count,
            "history_size": len(self._history),
            "last_emotion": self._last_signature["emotions"]["primary"] if self._last_signature else None,
            "last_intensity": self._last_signature["intensity"] if self._last_signature else 0.0,
            "storage_path": str(self.storage_path)
        }

    def _calculate_valence(self, word_set: set, total_words: int) -> float:
        """Calculate valence (-1 negative to +1 positive)."""
        pos_count = len(word_set & POSITIVE_WORDS)
        neg_count = len(word_set & NEGATIVE_WORDS)
        if pos_count + neg_count == 0:
            return 0.0
        raw = (pos_count - neg_count) / max(total_words, 1) * 10
        return max(-1.0, min(1.0, raw))

    def _calculate_arousal(self, word_set: set, total_words: int) -> float:
        """Calculate arousal (0 calm to 1 excited)."""
        high = len(word_set & HIGH_AROUSAL_WORDS)
        low = len(word_set & LOW_AROUSAL_WORDS)
        if high + low == 0:
            return 0.5
        raw = 0.5 + (high - low) / max(total_words, 1) * 5
        return max(0.0, min(1.0, raw))

    def _calculate_dominance(self, word_set: set, total_words: int) -> float:
        """Calculate dominance (0 submissive to 1 dominant)."""
        dom = len(word_set & DOMINANCE_WORDS)
        sub = len(word_set & SUBMISSIVE_WORDS)
        if dom + sub == 0:
            return 0.5
        raw = 0.5 + (dom - sub) / max(total_words, 1) * 5
        return max(0.0, min(1.0, raw))

    def _score_emotions(self, word_set: set, total_words: int) -> Dict[str, float]:
        """Score each emotion category."""
        scores = {}
        for emotion, config in EMOTION_PATTERNS.items():
            overlap = len(word_set & config["words"])
            score = overlap / max(total_words, 1) * 10
            scores[emotion] = min(1.0, score)

        # If no strong emotions detected, default to contemplation
        if all(v < 0.1 for v in scores.values()):
            scores["contemplation"] = 0.3

        return scores

    def _empty_signature(self) -> Dict[str, Any]:
        """Return empty/default emotional signature."""
        return {
            "emotional_signature": {
                "vad": {"valence": 0.0, "arousal": 0.5, "dominance": 0.5},
                "emotions": {"primary": "neutral", "secondary": "neutral", "scores": {}},
                "intensity": 0.0,
                "authenticity": 0.5,
                "resonance": 0.3
            },
            "context": {},
            "timestamp": datetime.now().isoformat()
        }


def create_midas_engine(storage_path: Optional[Path] = None) -> MidasEmotionalEngine:
    """Factory function to create MIDAS engine."""
    if isinstance(storage_path, str):
        storage_path = Path(storage_path)
    return MidasEmotionalEngine(storage_path=storage_path)
