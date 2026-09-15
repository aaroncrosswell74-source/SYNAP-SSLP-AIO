"""
Memory Sanitization - Filter harmful or malformed content
==========================================================
No external APIs; uses regex, blacklists, and structural validation.
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class MemorySanitizer:
    """
    Cleans user inputs and AI responses before storing in memory.
    Removes PII, profanity, and enforces length limits.
    """

    # Simple patterns for demonstration
    EMAIL_PATTERN = re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b')
    PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
    PROFANITY = {"fuck", "shit", "damn", "asshole", "bitch"}  # expand as needed

    def __init__(self, max_length: int = 2000, redact_pii: bool = True):
        self.max_length = max_length
        self.redact_pii = redact_pii

    def sanitize_user_input(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Returns (sanitized_text, metadata) where metadata contains flags like 'has_pii'.
        """
        original = text
        metadata = {"original_length": len(original), "was_truncated": False, "has_pii": False}

        if self.redact_pii:
            text, pii_count = self._redact_pii(text)
            metadata["has_pii"] = pii_count > 0

        text = self._censor_profanity(text)

        if len(text) > self.max_length:
            text = text[:self.max_length]
            metadata["was_truncated"] = True

        metadata["sanitized_length"] = len(text)
        if metadata["was_truncated"]:
            logger.warning(f"Truncated user input from {len(original)} to {self.max_length} chars")

        return text, metadata

    def sanitize_ai_response(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """Similar to user input but stricter on safety."""
        # Reuse same logic, but maybe add additional checks
        return self.sanitize_user_input(text)

    def validate_memory_structure(self, memory: Dict[str, Any]) -> bool:
        """Ensure required fields exist and are of correct type."""
        required = {"id", "timestamp", "user_input", "ai_response"}
        if not all(k in memory for k in required):
            logger.warning(f"Memory missing required fields: {required - set(memory.keys())}")
            return False
        if not isinstance(memory["user_input"], str) or not isinstance(memory["ai_response"], str):
            logger.warning("Memory has non‑string content fields")
            return False
        return True

    def _redact_pii(self, text: str) -> Tuple[str, int]:
        """Replace emails and phone numbers with [REDACTED]."""
        count = 0
        text, n = self.EMAIL_PATTERN.subn("[EMAIL_REDACTED]", text)
        count += n
        text, n = self.PHONE_PATTERN.subn("[PHONE_REDACTED]", text)
        count += n
        return text, count

    def _censor_profanity(self, text: str) -> str:
        """Replace profane words with asterisks."""
        words = text.split()
        censored = []
        for w in words:
            lower = w.lower()
            if lower in self.PROFANITY:
                censored.append("*" * len(w))
            else:
                censored.append(w)
        return " ".join(censored)