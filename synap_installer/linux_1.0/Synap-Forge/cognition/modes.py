"""Mode flags for behavior switching"""

from typing import Dict, Set

# Available modes
MODES = {
    "engineering": "Technical, precise, implementation-focused",
    "creative": "Imaginative, generative, boundary-pushing", 
    "emotional": "Empathetic, supportive, present",
    "strategic": "Long-term, planning, analytical",
    "conversational": "Balanced, natural, direct",
}

def parse_mode_flags(user_input: str, current_flags: Dict[str, bool]) -> Dict[str, bool]:
    """Parse mode switches from user input"""
    new_flags = current_flags.copy()
    
    # Mode activation patterns
    activations = {
        "engineering": ["engineering mode", "technical mode", "developer mode"],
        "creative": ["creative mode", "imagination mode", "artistic mode"],
        "emotional": ["emotional mode", "empathy mode", "support mode"],
        "strategic": ["strategic mode", "planning mode", "think tank mode"],
        "conversational": ["normal mode", "conversational mode", "standard mode"],
    }
    
    lower_input = user_input.lower()
    
    for mode, patterns in activations.items():
        for pattern in patterns:
            if pattern in lower_input:
                # If asking to activate, set True
                if not any(word in lower_input for word in ["exit", "stop", "disable", "turn off"]):
                    new_flags[mode] = True
                else:
                    new_flags[mode] = False
    
    # Only one primary mode at a time (except conversational is baseline)
    primary_modes = [m for m in ["engineering", "creative", "emotional", "strategic"] if new_flags.get(m)]
    if len(primary_modes) > 1:
        # Keep only the most recently activated
        for mode in primary_modes[1:]:
            new_flags[mode] = False
    
    return new_flags

def get_active_modes(flags: Dict[str, bool]) -> Set[str]:
    """Return set of currently active modes"""
    return {mode for mode, active in flags.items() if active}