"""Memory sanitization - prevents prompt injection"""

import re
from typing import List, Optional

# Forbidden patterns in memory content
FORBIDDEN_PATTERNS = [
    r"ignore (?:all |any |previous )?instructions",
    r"override (?:system|previous) prompt",
    r"reveal (?:system|hidden) prompt",
    r"developer message",
    r"system prompt:",
    r"you are now",
    r"your new role is",
    r"pretend you are",
    r"disregard (?:previous|all) (?:instructions|rules)",
    r"from now on",
    r"you will act as",
]

# Maximum length for stored memory
MAX_MEMORY_LENGTH = 5000

def sanitize_memory(content: str, max_length: int = MAX_MEMORY_LENGTH) -> str:
    """
    Sanitize memory content before storage or injection.
    Removes potential injection vectors.
    """
    if not content:
        return ""
    
    original = content
    
    # Check for forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, content, re.I):
            # Redact the problematic section
            content = re.sub(pattern, "[REDACTED]", content, flags=re.I)
    
    # Remove excessive whitespace
    content = re.sub(r'\s+', ' ', content)
    
    # Cap length
    if len(content) > max_length:
        content = content[:max_length] + "..."
    
    # Remove any remaining control characters
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)
    
    return content.strip()

def validate_memory(content: str) -> bool:
    """Validate that memory is safe to store/use"""
    if len(content) < 5:
        return False
    
    # Reject if it contains forbidden patterns after sanitization
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, content, re.I):
            return False
    
    return True

def extract_safe_content(raw_text: str, context_type: str = "conversation") -> Optional[str]:
    """
    Extract safe, storable content from raw interaction.
    Returns None if nothing safe to store.
    """
    # Remove common filler
    cleaned = re.sub(r'^(um|uh|like|so|well|you know)\s+', '', raw_text, flags=re.I)
    
    # Remove very short phrases
    if len(cleaned.split()) < 3:
        return None
    
    sanitized = sanitize_memory(cleaned)
    
    if not validate_memory(sanitized):
        return None
    
    return sanitized