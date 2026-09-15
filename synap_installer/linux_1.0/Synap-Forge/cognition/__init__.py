"""
Cognition Module - The analytical substrate for structural metacognition.

Monitors processing anomalies, detects semantic drift, calculates system 
uncertainty metrics, and executes multi-agent or multi-stage arbitration.
"""

from .confidence import evaluate_confidence
from .uncertainty import UncertaintyCalculator
from .contradiction import ContradictionDetector
from .semantic_drift import DriftAnalyzer
from .arbitration import CognitiveArbitrator

__all__ = [
    "evaluate_confidence",
    "UncertaintyCalculator",
    "ContradictionDetector",
    "DriftAnalyzer",
    "CognitiveArbitrator",
]
