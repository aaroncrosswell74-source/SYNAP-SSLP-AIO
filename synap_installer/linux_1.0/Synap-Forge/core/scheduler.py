"""
Parallel Cognitive Scheduler - executes multiple channels concurrently.
"""

import asyncio
import uuid
import time
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field

from .arbitration import ArbitrationEngine, ArbitrationResult  # defined below
from .budget import CognitiveBudget


@dataclass
class CognitiveChannel:
    """A bounded execution lane."""
    channel_id: str
    name: str
    processor: Callable[..., Any]
    priority: int = 1
    timeout_ms: float = 500.0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    async def execute(self, *args, **kwargs) -> Any:
        if not self.enabled:
            return None
        try:
            return await asyncio.wait_for(self.processor(*args, **kwargs), timeout=self.timeout_ms / 1000.0)
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            return None
    
    @staticmethod
    def create(name: str, processor: Callable[..., Any], priority: int = 1) -> 'CognitiveChannel':
        return CognitiveChannel(
            channel_id=str(uuid.uuid4()),
            name=name,
            processor=processor,
            priority=priority,
        )


class ParallelScheduler:
    """Executes registered channels in parallel and arbitrates their outputs."""
    
    def __init__(self, arbitration_engine: Optional[ArbitrationEngine] = None):
        self.channels: List[CognitiveChannel] = []
        self.arbitration = arbitration_engine or ArbitrationEngine()
    
    def register_channel(self, channel: CognitiveChannel):
        self.channels.append(channel)
    
    async def execute(self, *args, **kwargs) -> ArbitrationResult:
        """Run all enabled channels concurrently and arbitrate."""
        tasks = []
        for channel in self.channels:
            if channel.enabled:
                tasks.append(asyncio.create_task(channel.execute(*args, **kwargs)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        named_results = {}
        for idx, result in enumerate(results):
            named_results[self.channels[idx].name] = result
        
        return self.arbitration.arbitrate(named_results)