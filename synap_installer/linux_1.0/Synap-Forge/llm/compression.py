"""
Context Window Compressor - Cleans historical logs based on budget margins.
"""

import re
from typing import List, Dict, Any
from .tokenizer import MockContextTokenizer


class SlidingWindowCompressor:
    def __init__(self, max_allowed_tokens: int = 2048):
        self.tokenizer = MockContextTokenizer()
        self.max_allowed_tokens = max_allowed_tokens

    def prune_context_frames(self, history_segments: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Removes oldest non‑system entries if total token count exceeds max_allowed_tokens.
        System role messages are never evicted.
        """
        total_tokens = sum(
            self.tokenizer.count_tokens(seg.get("content", "")) for seg in history_segments
        )
        if total_tokens <= self.max_allowed_tokens:
            return history_segments

        # Protect all system messages
        system_msgs = [seg for seg in history_segments if seg.get("role") == "system"]
        mutable = [seg for seg in history_segments if seg.get("role") != "system"]

        # Evict oldest until budget satisfied or only one mutable remains
        while mutable:
            current_total = sum(
                self.tokenizer.count_tokens(s.get("content", "")) for s in system_msgs
            ) + sum(self.tokenizer.count_tokens(s.get("content", "")) for s in mutable)

            if current_total <= self.max_allowed_tokens or len(mutable) <= 1:
                break
            mutable.pop(0)  # drop oldest conversation turn

        return system_msgs + mutable

    def strip_intermediate_tags(self, raw_output: str) -> str:
        """Removes recursive reasoning tags like <THOUGHT>...</THOUGHT>."""
        clean = re.sub(r"<THOUGHT>.*?</THOUGHT>", "", raw_output, flags=re.DOTALL)
        return clean.strip()