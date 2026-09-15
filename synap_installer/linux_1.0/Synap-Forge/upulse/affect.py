"""Core affect model: combines valence, arousal, and dominance."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AffectState:
    valence: float      # -1.0 (negative) .. +1.0 (positive)
    arousal: float      # 0.0 (calm) .. 1.0 (excited)
    dominance: float    # 0.0 (submissive) .. 1.0 (dominant)

    def __post_init__(self):
        # Clamp to valid ranges
        object.__setattr__(self, "valence", max(-1.0, min(1.0, self.valence)))
        object.__setattr__(self, "arousal", max(0.0, min(1.0, self.arousal)))
        object.__setattr__(self, "dominance", max(0.0, min(1.0, self.dominance)))


class AffectModel:
    """Simple linear combination of valence/arousal contributions."""

    @staticmethod
    def from_lexical_metrics(clarity: float, dominance: float) -> AffectState:
        """
        Map pipe_2 clarity/dominance to valence/arousal/dominance.
        Clarity → valence (higher clarity → more positive valence)
        """
        valence = (clarity - 0.5) * 2.0          # 0..1 → -1..1
        arousal = 0.5 + (dominance - 0.5) * 0.5  # shift dominance to arousal
        return AffectState(valence, arousal, dominance)

    @staticmethod
    def combine(primary: AffectState, secondary: Optional[AffectState] = None,
                weight: float = 0.7) -> AffectState:
        """Weighted combination of two affect states."""
        if secondary is None:
            return primary
        return AffectState(
            valence=weight * primary.valence + (1 - weight) * secondary.valence,
            arousal=weight * primary.arousal + (1 - weight) * secondary.arousal,
            dominance=weight * primary.dominance + (1 - weight) * secondary.dominance,
        )