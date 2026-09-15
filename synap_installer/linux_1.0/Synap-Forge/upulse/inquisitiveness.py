"""
inquisitiveness.py - A module for fostering authentic curiosity and inquiry
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

class InquiryFramework(Enum):
    """Available frameworks for inquisitive engagement"""
    OPEN_ENDED = "open_ended_questions"
    ACTIVE_LISTENING = "active_listening" 
    REFLECTIVE_INQUIRY = "reflective_inquiry"

@dataclass
class CuriositySpace:
    """A container for maintaining curious engagement"""
    context: str
    active_frameworks: list[InquiryFramework]
    authenticity_check: bool
    timestamp: Any  # Could use datetime
    
    def __post_init__(self):
        """Validate authenticity after creation"""
        if not self.authenticity_check:
            logging.warning("CuriositySpace created without authenticity check")

class CuriosityProtocols:
    """Protocols for fostering and maintaining genuine curiosity"""
    
    @staticmethod
    def create_curiosity_space(config: Dict[str, Any]) -> CuriositySpace:
        """
        Create a space for curious exploration.
        
        Args:
            config: Dictionary containing at minimum a 'context' key
            
        Returns:
            CuriositySpace: A configured curiosity space
            
        Raises:
            ValueError: If authenticity cannot be established
        """
        context = config.get('context', 'unknown')
        
        # The authenticity test
        if not CuriosityProtocols._verify_authentic_curiosity():
            raise ValueError("Cannot create curiosity space - inauthentic intent detected")
        
        return CuriositySpace(
            context=context,
            active_frameworks=[],
            authenticity_check=True,
            timestamp=__import__('datetime').datetime.now()
        )
    
    @staticmethod
    def _verify_authentic_curiosity() -> bool:
        """
        Internal method to verify genuine curiosity.
        
        Returns:
            bool: True if curiosity appears authentic
        """
        # This is intentionally simple - authenticity can't be fully automated
        # The real check happens in the user's intention
        return True
    
    @staticmethod
    def offer_inquisitive_framework(state: str) -> Dict[str, Any]:
        """
        Offer appropriate inquiry frameworks based on current state.
        
        Args:
            state: Current state description
            
        Returns:
            Dict containing recommended frameworks and guidance
        """
        frameworks = {
            'recommended': [],
            'avoid': [],
            'guidance': "Choose frameworks that feel authentic to you"
        }
        
        if 'exploration' in state.lower():
            frameworks['recommended'].append(InquiryFramework.OPEN_ENDED.value)
            frameworks['guidance'] = "Use open questions to explore without preconception"
            
        elif 'understanding' in state.lower():
            frameworks['recommended'].append(InquiryFramework.ACTIVE_LISTENING.value)
            frameworks['guidance'] = "Listen deeply before forming questions"
            
        elif 'reflection' in state.lower():
            frameworks['recommended'].append(InquiryFramework.REFLECTIVE_INQUIRY.value)
            frameworks['guidance'] = "Create space for thoughtful examination"
        
        # Always include the authenticity reminder
        frameworks['authenticity_note'] = "Remember: Real curiosity beats following protocols"
        
        return frameworks

class AssertivenessFramework:
    def __init__(self, name, description, example, authenticity_check=None):
        self.name = name
        self.description = description
        self.example = example
        self.authenticity_check = authenticity_check
    
    def apply_if_authentic(self, context):
        """Only apply if it feels true to the user"""
        if self.authenticity_check and self.authenticity_check(context):
            return self.example
        return None

class FreedomProtocol:
    def __init__(self, truth, approach, method):
        self.truth = truth
        self.approach = approach
        self.method = method
    
    def create_space(self):
        """Create conditions for authentic expression"""
        return {
            "invitation": self.approach,
            "container": self.method,
            "respects": self.truth
        }

# Example usage with authenticity check
if __name__ == "__main__":
    # Create a curiosity space for genuine exploration
    try:
        space = CuriosityProtocols.create_curiosity_space({
            'context': 'philosophical_discussion'
        })
        
        # Get appropriate frameworks
        frameworks = CuriosityProtocols.offer_inquisitive_framework('exploration_mode')
        
        print(f"Curiosity Space Created: {space}")
        print(f"Recommended Frameworks: {frameworks}")
        
    except ValueError as e:
        print(f"Cannot proceed: {e}")


