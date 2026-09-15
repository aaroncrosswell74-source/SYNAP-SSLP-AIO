# config/env_loader.py
"""Secure environment loader with validation"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import json

class SecureEnv:
    """Production-safe environment loader"""
    
    _instance = None
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self, env_path: Optional[Path] = None):
        """Load environment with proper parsing"""
        if self._loaded:
            return
        
        # Explicit path
        if env_path and env_path.exists():
            load_dotenv(env_path)
        else:
            # Default locations
            for path in [
                Path.cwd() / ".env",
                Path("/opt/synap-forge/config/.env"),
                Path.home() / ".config/synap-forge/.env"
            ]:
                if path.exists():
                    load_dotenv(path)
                    break
        
        # Validate required variables
        required = [
            "ASSISTANT_NAME",
            "CONTENT_MODE",
            "RECURSION_MAX_DEPTH"
        ]
        
        missing = [r for r in required if not os.getenv(r)]
        if missing:
            raise EnvironmentError(
                f"Missing required env vars: {', '.join(missing)}"
            )
        
        self._loaded = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get typed environment value"""
        value = os.getenv(key, default)
        
        # Type inference
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes")
        elif isinstance(default, int):
            return int(value)
        elif isinstance(default, float):
            return float(value)
        elif isinstance(default, list):
            return json.loads(value) if value else default
        return value
    
    def get_required(self, key: str) -> str:
        """Get required value, raise if missing"""
        value = os.getenv(key)
        if value is None:
            raise EnvironmentError(f"Required env var: {key}")
        return value

env = SecureEnv()