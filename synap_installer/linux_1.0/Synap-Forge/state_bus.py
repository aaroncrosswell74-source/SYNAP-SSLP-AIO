#!/usr/bin/env python3
"""
State Bus - Atomic State Management with Commands
"""

import json
import os
import time
import fcntl
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

class StateBus:
    """Atomic State Bus with command/state separation"""
    
    def __init__(self, base_path="state_bus"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        # Create subdirectories
        self._ensure_dir("commands/pending")
        self._ensure_dir("commands/processing")
        self._ensure_dir("commands/complete")
        self._ensure_dir("state")
        self._ensure_dir("registry")
    
    def _ensure_dir(self, subdir: str):
        (self.base_path / subdir).mkdir(parents=True, exist_ok=True)
    
    def write(self, service: str, payload: dict, subdir: str = "state") -> dict:
        """Atomic write with metadata"""
        data = {
            "schema_version": 1,
            "service": service,
            "status": payload.get("status", "ok"),
            "timestamp": datetime.now().isoformat(),
            "monotonic": time.monotonic(),
            "sequence": self._next_sequence(service),
            "payload": payload
        }
        
        path = self.base_path / subdir / f"{service}.json"
        tmp_path = path.with_suffix(".tmp")
        
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
        
        return data
    
    def read(self, service: str, subdir: str = "state") -> Optional[dict]:
        """Read latest state"""
        path = self.base_path / subdir / f"{service}.json"
        if not path.exists():
            return None
        
        with open(path, "r") as f:
            return json.load(f)
    
    def _next_sequence(self, service: str) -> int:
        """Get next sequence number"""
        seq_path = self.base_path / "state" / f"{service}.seq"
        if seq_path.exists():
            with open(seq_path, "r") as f:
                seq = int(f.read().strip())
            seq += 1
        else:
            seq = 1
        with open(seq_path, "w") as f:
            f.write(str(seq))
        return seq
