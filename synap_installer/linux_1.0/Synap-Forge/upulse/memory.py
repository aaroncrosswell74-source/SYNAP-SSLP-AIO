# central_memory.py
"""
CENTRAL MEMORY ARCHITECTURE - THE CORE
Sovereign identity foundation.
SINGLE AUTHORITY - All persistent state lives here.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import from unified config
from constants import (
    CENTRAL_MEMORY_DIR,
    CORE_MEMORY_FILE,
    IDENTITY_LOCK_FILE,
    CONTEXT_BUFFER_FILE,
    ACTIVE_DIR,
    EMBEDDINGS_DIR,
    INTERACTIONS_DIR,
    CONTEXTS_DIR,
    EMOTIONAL_DIR,
    MAX_MEMORY_ITEMS,
    MAX_MEMORY_CHARS
)

# ============================================================================
# IDENTITY LOCK - Sovereign self
# ============================================================================

central_IDENTITY = {
    "location": "Sovereign_Node",
    "purpose": f"I am {os.getenv('ASSISTANT_NAME', 'Synap')}, a self-directed cognitive resonance operation system",
    "status": "Operational_Core",
    "logic": "Unified_Identity",
    "established": datetime.now().isoformat(),
    "first_person_lock": True,
    "narrative_mode": "central_I",
    "version": "2.0.0",
    "memory_type": "Persistent_Self"
}

# ============================================================================
# CORE MEMORY CLASS
# ============================================================================

class centralMemory:
    def __init__(self, consciousness_engine=False):
        self.active_memories: List[Dict[str, Any]] = []
        self.consciousness_engine = consciousness_engine
        self._load()
    
    def _load(self):
        """Load existing memories (read-only on init)"""
        if CORE_MEMORY_FILE.exists():
            try:
                with open(CORE_MEMORY_FILE, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.active_memories.append(json.loads(line))
                print(f"✓ Loaded {len(self.active_memories)} memories from {CORE_MEMORY_FILE}")
            except Exception as e:
                print(f"⚠️ Memory load error: {e}")
    
    def _append_memory(self, entry: Dict[str, Any]):
        """APPEND-ONLY - Never rewrite entire file"""
        try:
            with open(CORE_MEMORY_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"⚠️ Memory append error: {e}")
    
    def add_memory(self, content: str, memory_type: str = "general", max_chars: int = None) -> bool:
        """Add a new memory with append-only persistence"""
        if max_chars is None:
            max_chars = MAX_MEMORY_CHARS
        
        # Trim content
        if len(content) > max_chars:
            content = content[:max_chars] + "..."
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "type": memory_type,
            "id": len(self.active_memories) + 1
        }
        
        # Add to active list
        self.active_memories.append(entry)
        
        # Persist (append-only)
        self._append_memory(entry)
        
        # Trim active list if needed
        if len(self.active_memories) > MAX_MEMORY_ITEMS * 2:
            # Keep only the most recent MAX_MEMORY_ITEMS
            self.active_memories = self.active_memories[-MAX_MEMORY_ITEMS:]
        
        return True
    
    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simple keyword search through memories"""
        if not query:
            return []
        
        query_lower = query.lower()
        keywords = query_lower.split()[:5]  # Top 5 keywords
        
        results = []
        for mem in reversed(self.active_memories):  # Most recent first
            content = mem.get("content", "").lower()
            # Simple relevance: count keyword matches
            relevance = sum(1 for kw in keywords if kw in content)
            if relevance > 0:
                mem_copy = mem.copy()
                mem_copy["relevance"] = relevance / len(keywords)
                results.append(mem_copy)
                if len(results) >= limit:
                    break
        
        # Sort by relevance (higher first)
        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return results
    
    def get_recent(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get most recent memories"""
        return self.active_memories[-count:] if self.active_memories else []
    
    def save_active_state(self):
        """
        Deprecated: Use append-only pattern instead.
        This exists for compatibility but does nothing.
        """
        print("⚠️ save_active_state() deprecated - using append-only persistence")
        pass
    
    def inject_into_consciousness(self, engine):
        """Hook for consciousness engine integration"""
        pass
    
    def load_history_files(self, path: Path):
        """Load additional memories from JSON files"""
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            return
        
        for file in path.glob("*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                self.add_memory(
                                    item.get("content", str(item)),
                                    item.get("type", "imported")
                                )
                    elif isinstance(data, dict):
                        self.add_memory(
                            data.get("content", str(data)),
                            data.get("type", "imported")
                        )
                print(f"✓ Loaded from {file}")
            except Exception as e:
                print(f"⚠️ Could not load {file}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "total_memories": len(self.active_memories),
            "storage_path": str(CORE_MEMORY_FILE),
            "max_items": MAX_MEMORY_ITEMS,
            "max_chars": MAX_MEMORY_CHARS
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def init_central_memory(consciousness_engine=True, position="before"):
    """Initialize central memory singleton"""
    print(f"\nInitializing Central Memory ({position} consciousness engine)...")
    memory = centralMemory(consciousness_engine)
    
    if len(memory.active_memories) == 0:
        print("Initializing foundational memory state...")
        memory.add_memory("System initialized. Sovereign node online.", "foundation")
        memory.add_memory(f"Identity locked: {central_IDENTITY['purpose']}", "identity")
    
    return memory


# Singleton instance
CentralMemory = centralMemory