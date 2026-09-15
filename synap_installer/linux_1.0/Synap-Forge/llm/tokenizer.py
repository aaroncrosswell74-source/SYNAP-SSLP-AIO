"""
Token Counter Substrate - Safely estimates context window consumption.
"""

import re
from typing import List


class MockContextTokenizer:
    def __init__(self, chars_per_token_ratio: float = 4.0):
        self.ratio = chars_per_token_ratio
        self.word_splitter = re.compile(r"\w+|[^\w\s]+")

    def encode(self, text: str) -> List[int]:
        """Returns deterministic placeholder token ids."""
        tokens = self.word_splitter.findall(text)
        return [hash(t) & 0xFFFF for t in tokens]

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, int(len(text) / self.ratio))

    def truncate_to_budget(self, text: str, max_tokens: int) -> str:
        estimated = self.count_tokens(text)
        if estimated <= max_tokens:
            return text
        allowed_chars = int(max_tokens * self.ratio)
        return text[:allowed_chars] + "\n...[CONTEXT TRUNCATED VIA BOUNDARY]"