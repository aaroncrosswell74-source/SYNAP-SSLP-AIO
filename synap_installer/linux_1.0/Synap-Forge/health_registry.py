# health_registry.py
"""
SYNAP·FORGE Health Registry
Provides component-level health reporting with layered endpoints
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Awaitable
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class ComponentHealth:
    """Health status for a single component"""
    name: str
    status: str  # "initializing", "ready", "degraded", "failed", "unknown"
    last_check: datetime = field(default_factory=datetime.now)
    last_success: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    check_count: int = 0
    failure_count: int = 0
    check_interval: int = 30  # seconds

class HealthRegistry:
    """Central registry for component health checks"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.components = {}
            cls._instance._started = False
            cls._instance._background_task = None
        return cls._instance
    
    def register(self, name: str, checker: Callable[[], Awaitable[tuple[str, Dict]]], 
                 interval: int = 30):
        """Register a component health checker"""
        self.components[name] = {
            "checker": checker,
            "health": ComponentHealth(
                name=name,
                status="initializing",
                check_interval=interval
            ),
            "last_run": None
        }
        logger.info(f"Registered health checker: {name}")
    
    async def check_component(self, name: str) -> ComponentHealth:
        """Run health check for a single component"""
        comp = self.components.get(name)
        if not comp:
            return ComponentHealth(name=name, status="unknown", error="Not registered")
        
        health = comp["health"]
        health.check_count += 1
        health.last_check = datetime.now()
        
        try:
            status, details = await comp["checker"]()
            health.status = status
            health.details = details
            health.error = None
            if status == "ready":
                health.last_success = datetime.now()
                health.failure_count = 0
            else:
                health.failure_count += 1
        except Exception as e:
            health.status = "failed"
            health.error = str(e)
            health.failure_count += 1
            logger.error(f"Health check failed for {name}: {e}")
        
        comp["last_run"] = datetime.now()
        return health
    
    async def check_all(self) -> Dict[str, ComponentHealth]:
        """Run health checks for all registered components"""
        results = {}
        for name in self.components:
            results[name] = await self.check_component(name)
        return results
    
    def get_summary(self) -> Dict[str, str]:
        """Get simple status summary"""
        return {
            name: comp["health"].status
            for name, comp in self.components.items()
        }
    
    def get_full_status(self) -> Dict[str, Any]:
        """Get full component status (safe for API responses)"""
        return {
            name: {
                "status": comp["health"].status,
                "last_check": comp["health"].last_check.isoformat(),
                "last_success": comp["health"].last_success.isoformat() if comp["health"].last_success else None,
                "error": comp["health"].error,
                "details": comp["health"].details,
                "check_count": comp["health"].check_count,
                "failure_count": comp["health"].failure_count
            }
            for name, comp in self.components.items()
        }
    
    def is_ready(self) -> bool:
        """Check if all components are ready"""
        return all(
            comp["health"].status == "ready"
            for comp in self.components.values()
        )
    
    async def start_background_checks(self):
        """Start background health checks"""
        if self._started:
            return
        
        self._started = True
        
        async def background_loop():
            while self._started:
                try:
                    # Check components that are due
                    now = datetime.now()
                    for name, comp in self.components.items():
                        if comp["last_run"] is None:
                            continue
                        elapsed = (now - comp["last_run"]).total_seconds()
                        if elapsed >= comp["health"].check_interval:
                            await self.check_component(name)
                    
                    await asyncio.sleep(5)  # Check every 5 seconds
                except Exception as e:
                    logger.error(f"Background health check error: {e}")
                    await asyncio.sleep(30)
        
        self._background_task = asyncio.create_task(background_loop())
        logger.info("Started background health checks")
    
    async def stop_background_checks(self):
        """Stop background health checks"""
        self._started = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped background health checks")

# Global instance
health_registry = HealthRegistry()