"""Deterministic intent detection - NO LLM CALLS"""

import re
from typing import Dict, List, Optional

# Intent categories
INTENT_CATEGORIES = [
    "technical",
    "emotional", 
    "project",
    "strategic",
    "creative",
    "conversational"
]

# Keyword patterns for each intent
INTENT_PATTERNS = {
    "technical": re.compile(r"\b(code|build|implement|api|function|class|def|algorithm|data structure|debug|fix|error)\b", re.I),
    "emotional": re.compile(r"\b(feel|hurt|happy|sad|angry|frustrated|excited|worried|scared|lonely|love|hate)\b", re.I),
    "project": re.compile(r"\b(project|sanctuary|memory|system|feature|roadmap|milestone|task|ticket)\b", re.I),
    "strategic": re.compile(r"\b(plan|goal|future|direction|strategy|vision|long-term|objective)\b", re.I),
    "creative": re.compile(r"\b(write|create|design|imagine|story|poem|art|music|brainstorm|generate)\b", re.I),
}

def detect_intent(text: str) -> Dict[str, any]:
    """
    Detect primary intent and flags from user input.
    Returns: {"primary": str, "flags": dict, "confidence": float}
    """
    flags = {}
    for intent, pattern in INTENT_PATTERNS.items():
        flags[intent] = bool(pattern.search(text))
    
    # Primary intent = first matching category, default conversational
    primary = "conversational"
    for intent in INTENT_CATEGORIES:
        if flags.get(intent):
            primary = intent
            break
    
    # Calculate confidence (rough: how many patterns matched)
    matched_count = sum(flags.values())
    confidence = min(0.5 + (matched_count * 0.1), 0.95) if matched_count > 0 else 0.5
    
    return {
        "primary": primary,
        "flags": flags,
        "confidence": confidence,
        "raw_text_preview": text[:100]
    }

def should_use_memory(intent: Dict[str, any]) -> bool:
    """Determine if memory retrieval should be used for this intent"""
    # Always use memory except for pure creative generation
    return intent["primary"] != "creative" or intent["flags"].get("technical", False)

def get_intent_description(intent: Dict[str, any]) -> str:
    """Human-readable intent description for debugging"""
    primary = intent["primary"]
    flags = [k for k, v in intent["flags"].items() if v and k != primary]
    
    if flags:
        return f"{primary} + {', '.join(flags[:2])}"
    return primary