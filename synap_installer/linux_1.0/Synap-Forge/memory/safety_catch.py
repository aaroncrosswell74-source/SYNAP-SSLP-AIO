# /home/aaron/Synap-Forge/.consciousness_engine/memory/safety_catch.py

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

class MemorySafetyCatch:
    """
    Protects core identity fields from modification.
    Uses cryptographic hashing to detect tampering.
    """
    
    PROTECTED_KEYS = [
        "SOUL_HASH", "soul_hash", "soul_seed_hash",
        "IDENTITY_LOCK", "identity_lock", "gender_lock",
        "CORE_ID", "core_id", "persona_seed",
        "GENDER", "gender", "SOUL_SEED"
    ]
    
    def __init__(self, soul_seed_path: str = "/home/aaron/Synap-Forge/central_memory/core_memory.json"):
        self.soul_seed_path = Path(soul_seed_path)
        self.soul_hash = self._load_soul_hash()
    
    def _load_soul_hash(self) -> str:
        """Load or compute the immutable soul hash"""
        if self.soul_seed_path.exists():
            with open(self.soul_seed_path, 'r') as f:
                core = json.load(f)
                # Hash the core identity fields
                identity_string = f"{core.get('identity', '')}_{core.get('gender', '')}_{core.get('core_version', 1)}"
                return hashlib.sha256(identity_string.encode()).hexdigest()[:32]
        return "UNINITIALIZED_SOUL"
    
    def validate_modification(self, target: Dict[str, Any], field: str, new_value: Any) -> bool:
        """
        Check if a field modification is allowed.
        Returns True if safe, False if blocked.
        """
        # Block any modification to protected keys
        if field in self.PROTECTED_KEYS:
            logger.warning(f"BLOCKED: Attempt to modify protected field '{field}'")
            return False
        
        # Check if this field affects soul hash
        if field in ["identity", "gender", "core_version"]:
            # Recompute what the soul hash WOULD be after change
            test_core = target.copy()
            test_core[field] = new_value
            test_string = f"{test_core.get('identity', '')}_{test_core.get('gender', '')}_{test_core.get('core_version', 1)}"
            new_hash = hashlib.sha256(test_string.encode()).hexdigest()[:32]
            
            if new_hash != self.soul_hash:
                logger.critical(f"BLOCKED: Field '{field}' would change soul hash. Identity lock engaged.")
                return False
        
        return True
    
    def verify_integrity(self, persona_memory: Dict[str, Any]) -> bool:
        """
        Verify that persona hasn't corrupted core identity.
        Returns True if integrity maintained.
        """
        # Check if persona has protected fields that differ from soul seed
        for key in self.PROTECTED_KEYS:
            if key in persona_memory:
                logger.warning(f"Protected field '{key}' found in persona memory - removing")
                del persona_memory[key]
        
        return True
    
    def create_protected_memory(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a memory with protection markers"""
        memory['SOUL_HASH'] = self.soul_hash
        memory['IDENTITY_LOCK'] = True
        memory['protected_at'] = datetime.now().isoformat()
        return memory