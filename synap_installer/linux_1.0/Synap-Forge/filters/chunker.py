"""Speech chunker - natural sentence boundary detection"""

import re
from typing import List, Optional

# Sentence boundary patterns (in order of preference)
SENTENCE_BOUNDARIES = [
    (re.compile(r'([.!?]+)\s+'), 1),      # Period, exclamation, question
    (re.compile(r'([,;:])\s+'), 2),        # Comma, semicolon, colon
    (re.compile(r'(\n\s*\n)'), 0),         # Paragraph break
    (re.compile(r'(\n)'), 3),              # Newline
]

class SpeechChunker:
    """
    Incremental sentence chunker for TTS pacing.
    Emits completed utterances, buffers partials.
    """
    
    def __init__(self, min_chunk_length: int = 20, max_chunk_length: int = 200):
        self.buffer = ""
        self.min_length = min_chunk_length
        self.max_length = max_chunk_length
        self._reset()
    
    def _reset(self):
        self.buffer = ""
        self._partial_emit = ""
    
    def feed(self, token: str) -> List[str]:
        """Feed token, return completed chunks"""
        self.buffer += token
        completed = []
        
        while True:
            chunk = self._extract_next_chunk()
            if chunk is None:
                break
            if len(chunk) >= self.min_length:
                completed.append(chunk.strip())
            self._partial_emit = ""
        
        return completed
    
    def _extract_next_chunk(self) -> Optional[str]:
        """Extract the next complete chunk from buffer"""
        
        # Try boundaries in priority order
        for pattern, priority in SENTENCE_BOUNDARIES:
            match = pattern.search(self.buffer)
            if match and match.start() >= self.min_length:
                end_pos = match.end()
                chunk = self.buffer[:end_pos]
                
                # Don't split if we're near max length without a boundary
                if len(chunk) > self.max_length and priority > 0:
                    # Find last space as fallback
                    last_space = chunk.rfind(' ', 0, self.max_length)
                    if last_space > self.min_length:
                        end_pos = last_space + 1
                        chunk = self.buffer[:end_pos]
                
                self.buffer = self.buffer[end_pos:]
                return chunk
        
        # If buffer getting too long, force a split at last space
        if len(self.buffer) > self.max_length * 1.5:
            last_space = self.buffer.rfind(' ', 0, self.max_length)
            if last_space > self.min_length:
                chunk = self.buffer[:last_space + 1]
                self.buffer = self.buffer[last_space + 1:]
                return chunk
        
        return None
    
    def flush(self) -> Optional[str]:
        """Flush remaining buffer"""
        if self.buffer.strip():
            remaining = self.buffer.strip()
            self.buffer = ""
            return remaining if len(remaining) >= self.min_length else None
        return None
    
    def reset(self):
        """Reset chunker state"""
        self._reset()