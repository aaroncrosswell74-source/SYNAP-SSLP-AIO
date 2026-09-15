#!/usr/bin/env python3
"""
Service Registry - Health and Capability Discovery
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

class ServiceRegistry:
    """Service registry with heartbeat and timeout detection"""
    
    def __init__(self, base_path="state_bus/registry"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def heartbeat(self, service: str, status: str, metadata: dict = None) -> dict:
        """Update service heartbeat with monotonic clock"""
        data = {
            "service": service,
            "status": status,
            "wall_time": datetime.now().isoformat(),
            "monotonic": time.monotonic(),
            "pid": os.getpid(),
            "metadata": metadata or {}
        }
        
        path = self.base_path / f"{service}.json"
        tmp_path = path.with_suffix(".tmp")
        
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
        
        return data
    
    def get_service(self, service: str) -> Optional[dict]:
        """Get service status"""
        path = self.base_path / f"{service}.json"
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None
    
    def get_all_services(self, timeout_seconds: int = 30) -> dict:
        """Get all services with heartbeat check"""
        result = {}
        now = time.monotonic()
        
        for path in self.base_path.glob("*.json"):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                
                last = data.get("monotonic", 0)
                elapsed = now - last
                
                data["healthy"] = elapsed < timeout_seconds
                data["elapsed_seconds"] = round(elapsed, 2)
                
                if elapsed >= timeout_seconds:
                    data["status"] = "timeout"
                
                result[data["service"]] = data
            except Exception:
                pass
        
        return result
    
    def get_health_summary(self) -> dict:
        """Get a summary of all service health"""
        services = self.get_all_services()
        total = len(services)
        healthy = sum(1 for s in services.values() if s.get("healthy", False))
        
        return {
            "total": total,
            "healthy": healthy,
            "degraded": total - healthy,
            "services": services,
            "timestamp": datetime.now().isoformat()
        }
