"""
EGO SYNTHESIZER - Minimalist Dynamic Identity
"""
import os
from typing import Dict, Any, List
from pathlib import Path

def synthesize_ego_prompt(state: Dict[str, Any], input: str = "") -> str:
    """
    Synthesize a prompt based on current state and input.
    Anchored to input to prevent drift.
    """
    name = state.get("name", "Synap")
    tag = state.get("tag", "User")
    mood = state.get("mood", "neutral")
    
    # Dynamic directives based on input
    directive = ""
    if "?" in input:
        directive = "Respond with analytical precision."
    elif "!" in input:
        directive = "Match the user's intensity."
    
    prompt = f"You are {name}. Current mood: {mood}. User is {tag}. {directive}"
    return prompt

def get_recent_context(limit: int = 5) -> List[Dict[str, str]]:
    """Placeholder for context retrieval."""
    return []
