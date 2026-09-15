#!/usr/bin/env python3
"""
MemoryStore - YOUR ACTUAL MEMORY SYSTEM
Redis + Chroma + JSON fallback
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try imports
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None


class MemoryStore:
    """YOUR Memory System - Redis + Chroma + JSON"""
    
    def __init__(self, storage_path: str = None):
        self.base_path = Path("/home/aaron/Synap-Forge/.consciousness_engine")
        self.central_memory = self.base_path / "central_memory"
        self.central_memory.mkdir(parents=True, exist_ok=True)
        
        # Connect Redis (THIS IS YOUR PRIMARY MEMORY!)
        self.redis = None
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)
                self.redis.ping()
                logger.info(f"✅ Redis connected - {self.redis.dbsize()} keys")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
        
        # Connect Chroma (YOUR VECTOR MEMORY!)
        self.chroma = None
        self.collection = None
        if CHROMA_AVAILABLE:
            try:
                self.chroma = chromadb.PersistentClient(
                    path=str(self.central_memory / "chroma")
                )
                collections = self.chroma.list_collections()
                if collections:
                    self.collection = collections[0]
                    logger.info(f"✅ Chroma connected: {self.collection.name} ({self.collection.count()} entries)")
                else:
                    # Create default collection
                    self.collection = self.chroma.create_collection("memories")
                    logger.info("✅ Chroma collection created")
            except Exception as e:
                logger.warning(f"Chroma not available: {e}")
        
        # Load core memory (your identity)
        self.core_path = self.central_memory / "core_memory.json"
        self.core_memory = self._load_core()
        
        logger.info("✅ MemoryStore ready")
    
    def _load_core(self) -> Dict:
        """Load core identity"""
        if self.core_path.exists():
            try:
                # Read line by line to handle multiple JSON objects
                with open(self.core_path, 'r') as f:
                    content = f.read()
                    # Find the first complete JSON object
                    import re
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        return json.loads(match.group())
            except Exception as e:
                logger.warning(f"Core load failed: {e}")
        return {"identity": "Synap-Forge", "version": "1.0.0"}
    
    def add_memory(self, content: str, memory_type: str = "interaction", 
                   user_id: str = "default", **kwargs) -> bool:
        """Add memory - PRIMARY: Redis, SECONDARY: Chroma"""
        
        memory = {
            "content": content,
            "type": memory_type,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        success = False
        
        # 1. PRIMARY: Save to Redis (working memory)
        if self.redis:
            try:
                key = f"chat:{user_id}"
                self.redis.rpush(key, json.dumps({
                    "role": "assistant" if memory_type == "response" else "user",
                    "content": content,
                    "timestamp": memory["timestamp"]
                }))
                self.redis.ltrim(key, -100, -1)  # Keep last 100
                success = True
                logger.debug("Memory saved to Redis")
            except Exception as e:
                logger.warning(f"Redis save failed: {e}")
        
        # 2. SECONDARY: Save to Chroma (vector memory)
        if self.collection:
            try:
                import time
                doc_id = f"{user_id}_{int(time.time())}_{hash(content[:20])}"
                self.collection.add(
                    documents=[content],
                    ids=[doc_id],
                    metadatas=[{
                        "type": memory_type, 
                        "user_id": user_id,
                        "timestamp": memory["timestamp"]
                    }]
                )
                success = True
                logger.debug("Memory saved to Chroma")
            except Exception as e:
                logger.warning(f"Chroma save failed: {e}")
        
        # 3. FALLBACK: Save to JSON (durable)
        try:
            interactions_dir = self.central_memory / "interactions"
            interactions_dir.mkdir(exist_ok=True)
            file_path = interactions_dir / f"{int(datetime.now().timestamp())}.json"
            with open(file_path, 'w') as f:
                json.dump(memory, f, indent=2)
        except:
            pass
        
        return success
    
    def search(self, query: str, limit: int = 5, user_id: str = "default") -> List[Dict]:
        """Search - PRIMARY: Redis, SECONDARY: Chroma"""
        results = []
        
        # 1. PRIMARY: Search Redis (recent context)
        if self.redis:
            try:
                key = f"chat:{user_id}"
                history = self.redis.lrange(key, -20, -1)
                for item in history:
                    try:
                        msg = json.loads(item)
                        content = msg.get("content", "")
                        if query.lower() in content.lower():
                            results.append({
                                "source": "redis",
                                "content": content[:500],
                                "role": msg.get("role", ""),
                                "timestamp": msg.get("timestamp", ""),
                                "_score": 0.9
                            })
                    except:
                        pass
            except Exception as e:
                logger.debug(f"Redis search failed: {e}")
        
        # 2. SECONDARY: Search Chroma (semantic)
        if self.collection:
            try:
                # Get recent entries from Chroma
                chroma_results = self.collection.get(limit=limit)
                if chroma_results and 'documents' in chroma_results:
                    for i, doc in enumerate(chroma_results['documents']):
                        if doc and query.lower() in doc.lower():
                            results.append({
                                "source": "chroma",
                                "content": doc[:500],
                                "_score": 0.7
                            })
            except Exception as e:
                logger.debug(f"Chroma search failed: {e}")
        
        # 3. FALLBACK: Search JSON
        try:
            interactions_dir = self.central_memory / "interactions"
            if interactions_dir.exists():
                for file_path in list(interactions_dir.glob("*.json"))[-10:]:
                    try:
                        with open(file_path, 'r') as f:
                            mem = json.load(f)
                            content = mem.get("content", "")
                            if query.lower() in content.lower():
                                results.append({
                                    "source": "json",
                                    "content": content[:500],
                                    "timestamp": mem.get("timestamp", ""),
                                    "_score": 0.5
                                })
                    except:
                        pass
        except:
            pass
        
        # Sort by score and deduplicate
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: x.get("_score", 0), reverse=True):
            content = r.get("content", "")
            if content and content not in seen:
                seen.add(content)
                unique.append(r)
        
        return unique[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        stats = {
            "core_identity": self.core_memory.get("identity", "Unknown"),
            "redis_available": self.redis is not None,
            "chroma_available": self.collection is not None,
        }
        
        if self.redis:
            try:
                stats["redis_keys"] = self.redis.dbsize()
                stats["chat_keys"] = len(self.redis.keys("chat:*"))
            except:
                pass
        
        if self.collection:
            try:
                stats["chroma_entries"] = self.collection.count()
            except:
                pass
        
        # Count JSON files
        interactions_dir = self.central_memory / "interactions"
        if interactions_dir.exists():
            stats["json_files"] = len(list(interactions_dir.glob("*.json")))
        
        return stats
    
    def get_recent(self, limit: int = 10, user_id: str = "default") -> List[Dict]:
        """Get recent memories from Redis"""
        results = []
        if self.redis:
            try:
                key = f"chat:{user_id}"
                history = self.redis.lrange(key, -limit, -1)
                for item in history:
                    try:
                        results.append(json.loads(item))
                    except:
                        pass
            except:
                pass
        return results
    
    def count(self) -> int:
        """Total memory count"""
        total = 0
        if self.redis:
            try:
                total += self.redis.dbsize()
            except:
                pass
        if self.collection:
            try:
                total += self.collection.count()
            except:
                pass
        return total
    
    def clear(self):
        """Clear memory (use with caution)"""
        if self.redis:
            try:
                self.redis.flushall()
                logger.warning("Redis cleared")
            except:
                pass
        if self.collection:
            try:
                # Chroma clear is more complex - just note it
                logger.warning("Chroma not cleared - manual deletion needed")
            except:
                pass

__all__ = ['MemoryStore']
