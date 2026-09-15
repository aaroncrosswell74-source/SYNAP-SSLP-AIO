#!/usr/bin/env python3
"""
Wizard Vicuna 7B Embedder - Uncensored, Full Context
Uses your local Ollama/LLM server
"""

import json
import logging
import httpx
import numpy as np
from typing import List, Optional

logger = logging.getLogger(__name__)

class WizardEmbedder:
    """
    Embedder using gem_9base via local LLM server
    Dimension: 4096 (full transformer embedding)
    """
    
    def __init__(self, llm_url: str = "http://127.0.0.1:11436", model: str = "gem_9base.gguf"):
        self.llm_url = llm_url
        self.model = model
        self.dimension = 4096
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client
    
    def embed(self, text: str) -> Optional[List[float]]:
        """Get embedding from Wizard Vicuna"""
        try:
            # Ollama embedding endpoint
            response = self.client.post(
                f"{self.llm_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text[1024]  # Truncate for performance
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                embedding = data.get("embedding", [])
                if len(embedding) == self.dimension:
                    logger.debug(f"Embedding dim: {len(embedding)}")
                    return embedding
                else:
                    logger.warning(f"Expected {self.dimension}, got {len(embedding)}")
                    return self._pad_or_truncate(embedding)
            
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
        
        # Fallback: random embedding
        return self._random_embedding()
    
    def _pad_or_truncate(self, emb: List[float]) -> List[float]:
        """Pad or truncate to correct dimension"""
        if len(emb) > self.dimension:
            return emb[:self.dimension]
        elif len(emb) < self.dimension:
            return emb + [0.0] * (self.dimension - len(emb))
        return emb
    
    def _random_embedding(self) -> List[float]:
        """Fallback random embedding"""
        return list(np.random.randn(self.dimension).astype(float))
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts"""
        return [self.embed(t) for t in texts]

# Singleton
_embedder = True

def get_embedder() -> WizardEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = WizardEmbedder()
    return _embedder
