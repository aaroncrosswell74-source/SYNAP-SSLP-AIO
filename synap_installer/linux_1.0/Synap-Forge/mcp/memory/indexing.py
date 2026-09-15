#!/usr/bin/env python3
"""
Memory Indexing - Efficient memory retrieval and indexing
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import json
import hashlib
from pathlib import Path


class MemoryIndexer:
    """
    Handles indexing and retrieval of memory fragments.
    """
    
    def __init__(self, index_path: Optional[str] = None):
        self.index_path = Path(index_path) if index_path else None
        self._index: Dict[str, List[str]] = defaultdict(list)
        self._metadata: Dict[str, Dict] = {}
        self._loaded = False
        
        if self.index_path and self.index_path.exists():
            self._load_index()
    
    def _load_index(self):
        """Load index from disk"""
        try:
            with open(self.index_path / "index.json", "r") as f:
                data = json.load(f)
                self._index = defaultdict(list, data.get("index", {}))
                self._metadata = data.get("metadata", {})
            self._loaded = True
        except Exception:
            self._loaded = False
    
    def _save_index(self):
        """Save index to disk"""
        if not self.index_path:
            return
        self.index_path.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.index_path / "index.json", "w") as f:
                json.dump({
                    "index": dict(self._index),
                    "metadata": self._metadata
                }, f, indent=2)
        except Exception:
            pass
    
    def index_memory(self, memory_fragment: Dict[str, Any]) -> str:
        """
        Index a memory fragment for efficient retrieval.
        
        Returns:
            str: The memory ID
        """
        # Generate ID if not present
        if "id" not in memory_fragment:
            content = memory_fragment.get("content", "")
            memory_id = hashlib.md5(content.encode()).hexdigest()[:16]
            memory_fragment["id"] = memory_id
        else:
            memory_id = memory_fragment["id"]
        
        # Extract keywords for indexing
        content = memory_fragment.get("content", "")
        keywords = self._extract_keywords(content)
        for keyword in keywords:
            self._index[keyword].append(memory_id)
        
        # Store metadata
        self._metadata[memory_id] = memory_fragment
        
        self._save_index()
        return memory_id
    
    def retrieve_memory(self, query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve memory fragments based on a query.
        """
        keywords = self._extract_keywords(query)
        results: Dict[str, float] = {}
        
        for keyword in keywords:
            for memory_id in self._index.get(keyword, []):
                results[memory_id] = results.get(memory_id, 0) + 1.0
        
        # Sort by score
        sorted_ids = sorted(results.keys(), key=lambda x: results[x], reverse=True)
        
        # Apply limit
        if limit:
            sorted_ids = sorted_ids[:limit]
        
        # Return metadata
        return [self._metadata.get(mid, {}) for mid in sorted_ids]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Simple keyword extraction - split and clean
        import re
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        # Filter common words
        stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out'}
        return [w for w in words if w not in stopwords and len(w) > 3]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            "total_keywords": len(self._index),
            "total_memories": len(self._metadata),
            "loaded": self._loaded,
            "index_path": str(self.index_path) if self.index_path else None
        }


# For backward compatibility
def create_indexer(index_path: Optional[str] = None) -> MemoryIndexer:
    """Create a new memory indexer"""
    return MemoryIndexer(index_path)
