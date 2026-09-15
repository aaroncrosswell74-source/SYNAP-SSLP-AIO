"""
SYNAP·FORGE Boot State Machine
Manages deterministic startup sequence
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)

class BootState(Enum):
    """Boot states in order"""
    UNINITIALIZED = auto()
    CONFIG_LOADED = auto()
    LOGGING_READY = auto()
    REDIS_CONNECTED = auto()
    CHROMA_READY = auto()
    MEMORY_LOADED = auto()
    COGNITION_READY = auto()
    EMOTION_READY = auto()
    RL_READY = auto()
    SAFETY_READY = auto()
    WEBSOCKET_READY = auto()
    SERVER_READY = auto()
    
    def __lt__(self, other):
        return self.value < other.value

@dataclass
class BootStatus:
    """Current boot status"""
    state: BootState = BootState.UNINITIALIZED
    timestamp: datetime = field(default_factory=datetime.now)
    components: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    
    def transition(self, new_state: BootState, component_data: Optional[Dict] = None):
        """Transition to a new boot state"""
        self.state = new_state
        self.timestamp = datetime.now()
        if component_data:
            self.components[new_state.name] = component_data
        if new_state == BootState.CONFIG_LOADED and self.start_time is None:
            self.start_time = self.timestamp
        if new_state == BootState.SERVER_READY:
            self.completion_time = self.timestamp
        logger.info(f"Boot transition: {new_state.name}")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            "state": self.state.name,
            "timestamp": self.timestamp.isoformat(),
            "components": self.components,
            "errors": self.errors,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }

class BootManager:
    """Manages deterministic startup sequence"""
    
    def __init__(self):
        self.status = BootStatus()
        self._handlers: Dict[BootState, Dict] = {}
        self._completed = set()
    
    def register(self, state: BootState, handler: Callable[[], Awaitable[Any]], 
                 required: List[BootState] = None, timeout: int = 30):
        """Register a boot step"""
        self._handlers[state] = {
            "handler": handler,
            "required": required or [],
            "timeout": timeout,
            "completed": False
        }
        logger.debug(f"Registered boot step: {state.name}")
    
    async def boot(self) -> BootStatus:
        """Execute the boot sequence"""
        logger.info("Starting SYNAP·FORGE boot sequence...")
        
        sorted_states = sorted(self._handlers.keys(), key=lambda s: s.value)
        
        for state in sorted_states:
            config = self._handlers[state]
            
            for req in config["required"]:
                if req not in self._completed:
                    error = f"Required state {req.name} not completed for {state.name}"
                    logger.error(error)
                    self.status.errors.append({
                        "state": state.name,
                        "error": error,
                        "timestamp": datetime.now().isoformat()
                    })
                    return self.status
            
            try:
                logger.info(f"Boot step: {state.name}")
                result = await asyncio.wait_for(
                    config["handler"](),
                    timeout=config["timeout"]
                )
                self.status.transition(state, result)
                self._completed.add(state)
                config["completed"] = True
                logger.info(f"Boot step complete: {state.name}")
            except asyncio.TimeoutError:
                error = f"Boot step {state.name} timed out after {config['timeout']}s"
                logger.error(error)
                self.status.errors.append({
                    "state": state.name,
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                })
                return self.status
            except Exception as e:
                error = f"Boot step {state.name} failed: {e}"
                logger.error(error)
                self.status.errors.append({
                    "state": state.name,
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                })
                return self.status
        
        self.status.transition(BootState.SERVER_READY)
        elapsed = (datetime.now() - self.status.start_time).total_seconds()
        logger.info(f"SYNAP·FORGE boot complete in {elapsed:.2f}s")
        return self.status
    
    def get_boot_progress(self) -> Dict:
        """Get boot progress for API responses"""
        total = len(self._handlers)
        completed = len([s for s in self._handlers.values() if s["completed"]])
        
        return {
            "state": self.status.state.name,
            "progress": f"{completed}/{total}",
            "completed": [s.name for s in self._completed],
            "pending": [s.name for s in self._handlers if not self._handlers[s]["completed"]]
        }

# Global instance
boot_manager = BootManager()
