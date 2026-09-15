import os
# /home/aaron/Synap-Forge/.consciousness_engine/memory/chroma_indexer.py

import chromadb
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ChromaEmotionalIndexer:
    """
    ChromaDB vector indexer with emotional metadata tagging.
    Updates existing entries instead of overwriting.
    """
    
    def __init__(self, chroma_host: str = "127.0.0.1", chroma_port: int = 8001):
        self.client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        self.collection_name = "meena_emotional_memory"
        self.collection = self._get_or_create_collection()
        
        # Protected fields (cannot be modified after creation)
        self.PROTECTED_FIELDS = {
            "SOUL_HASH", "IDENTITY_LOCK", "GENDER_LOCK", 
            "soul_seed_hash", "identity_lock", "core_id"
        }
    
    def _get_or_create_collection(self):
        """Get existing collection or create new one"""
        try:
            existing = self.client.get_collection(self.collection_name)
            logger.info(f"Loaded existing collection: {self.collection_name}")
            return existing
        except:
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine", "created_by": os.getenv("ASSISTANT_NAME", "Synap")}
            )
            logger.info(f"Created new collection: {self.collection_name}")
            return collection
    
    def update_emotional_weight(
        self, 
        memory_id: str, 
        emotional_metrics: Dict[str, float],
        force: bool = False
    ) -> bool:
        """
        Update emotional metadata for an existing memory.
        
        Args:
            memory_id: Unique memory identifier
            emotional_metrics: Dict with valence, arousal, dominance, etc.
            force: If True, bypass safety checks (requires --rebuild-all)
        
        Returns:
            True if updated, False if skipped due to protection
        """
        try:
            # Get existing entry
            existing = self.collection.get(ids=[memory_id])
            
            if not existing['ids']:
                logger.warning(f"Memory {memory_id} not found in Chroma")
                return False
            
            # Extract current metadata
            current_metadata = existing['metadatas'][0] if existing['metadatas'] else {}
            
            # PROTECTION: Check for locked fields
            for protected in self.PROTECTED_FIELDS:
                if protected in current_metadata and not force:
                    logger.warning(f"Cannot modify protected field '{protected}' for {memory_id}. Use --force or --rebuild-all")
                    return False
            
            # Merge new emotional metrics (don't overwrite core fields)
            updated_metadata = current_metadata.copy()
            updated_metadata.update({
                f"emotional_{k}": v for k, v in emotional_metrics.items()
            })
            updated_metadata["last_emotional_update"] = datetime.now().isoformat()
            
            # Update in Chroma
            self.collection.update(
                ids=[memory_id],
                metadatas=[updated_metadata]
            )
            
            logger.debug(f"Updated emotional weights for {memory_id}: {emotional_metrics}")
            return True
            
        except Exception as e:
            logger.error(f"Chroma update failed for {memory_id}: {e}")
            return False
    
    def get_memory_with_emotion(self, memory_id: str) -> Optional[Dict]:
        """Retrieve memory including emotional metadata"""
        try:
            result = self.collection.get(ids=[memory_id])
            if result['ids']:
                return {
                    "id": result['ids'][0],
                    "document": result['documents'][0] if result['documents'] else None,
                    "metadata": result['metadatas'][0] if result['metadatas'] else {},
                    "embedding": result['embeddings'][0] if result['embeddings'] else None
                }
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
        return None
    
    def rebuild_all(self, memory_data: List[Dict], force: bool = False):
        """
        FULL REBUILD - Only triggered by --rebuild-all flag.
        Wipes collection and recreates from source.
        """
        if not force:
            logger.error("Rebuild requires --rebuild-all flag for safety")
            return False
        
        logger.warning("🔥 FORCE REBUILD INITIATED - Wiping existing collection")
        
        # Delete existing collection
        try:
            self.client.delete_collection(self.collection_name)
        except:
            pass
        
        # Recreate collection
        self.collection = self._get_or_create_collection()
        
        # Bulk insert all memories with their emotional weights
        ids = []
        documents = []
        metadatas = []
        embeddings = []  # If you have precomputed embeddings
        
        for mem in memory_data:
            # Skip if missing ID
            if not mem.get('id'):
                continue
            
            ids.append(mem['id'])
            documents.append(mem.get('content', mem.get('user_input', '')))
            
            # Build metadata with protection markers
            metadata = {
                "timestamp": mem.get('timestamp', datetime.now().isoformat()),
                "source": mem.get('source', 'user'),
                "importance": mem.get('importance', 0.5),
                "SOUL_HASH": self._compute_soul_hash(mem),
                "IDENTITY_LOCK": mem.get('gender_locked', True),
            }
            
            # Add emotional metrics if available
            if 'emotional' in mem:
                for k, v in mem['emotional'].items():
                    metadata[f"emotional_{k}"] = v
            
            metadatas.append(metadata)
            
            # Add embedding if available
            if 'embedding' in mem:
                embeddings.append(mem['embedding'])
        
        # Batch insert (Chroma handles chunking)
        if embeddings:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
        else:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
        
        logger.info(f"Rebuilt collection with {len(ids)} memories")
        return True
    
    def _compute_soul_hash(self, memory: Dict) -> str:
        """Compute immutable hash for soul-seed protection"""
        core_fields = memory.get('core_fields', {})
        hash_input = f"{core_fields.get('identity', '')}_{core_fields.get('gender', '')}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


# Standalone rebuild script
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--rebuild-all', action='store_true', help='Force full Chroma rebuild')
    parser.add_argument('--source', type=str, help='Source JSON file with memories')
    args = parser.parse_args()
    
    if args.rebuild_all and args.source:
        with open(args.source, 'r') as f:
            memories = json.load(f)
        
        indexer = ChromaEmotionalIndexer()
        indexer.rebuild_all(memories, force=True)
        print(f"✅ Rebuilt Chroma with {len(memories)} memories")
    else:
        print("Usage: python chroma_indexer.py --rebuild-all --source memories.json")