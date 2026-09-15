"""
Cognitive Pipeline - orchestrates sequential stages.

Each stage is a callable that takes a ProcessingState and returns a new one.
Supports interruption, telemetry hooks, and timeouts.
"""

import asyncio
import logging
from typing import List, Callable, Awaitable, Optional, Any
from dataclasses import dataclass, field

from .state import ProcessingState
from .budget import CognitiveBudget

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    """Result of executing a pipeline stage."""
    state: ProcessingState
    stage_name: str
    duration_ms: float
    error: Optional[Exception] = None
    interrupted: bool = False


class PipelineStage:
    """Wrapper for a stage function with metadata."""
    
    def __init__(self, name: str, func: Callable[[ProcessingState], Awaitable[ProcessingState]], timeout_ms: float = 5000):
        self.name = name
        self.func = func
        self.timeout_ms = timeout_ms
    
    async def execute(self, state: ProcessingState) -> StageResult:
        import time
        start = time.time()
        try:
            # Run with timeout
            result_state = await asyncio.wait_for(self.func(state), timeout=self.timeout_ms / 1000.0)
            duration = (time.time() - start) * 1000
            return StageResult(state=result_state, stage_name=self.name, duration_ms=duration)
        except asyncio.TimeoutError:
            duration = (time.time() - start) * 1000
            logger.warning(f"Stage {self.name} timed out after {duration:.0f}ms")
            return StageResult(state=state, stage_name=self.name, duration_ms=duration,
                               error=TimeoutError(f"Stage {self.name} timeout"), interrupted=True)
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Stage {self.name} failed: {e}")
            return StageResult(state=state, stage_name=self.name, duration_ms=duration,
                               error=e, interrupted=True)


class CognitivePipeline:
    """Sequential pipeline with interrupt support."""
    
    def __init__(self, stages: List[PipelineStage] = None, budget: Optional[CognitiveBudget] = None):
        self.stages = stages or []
        self.budget = budget or CognitiveBudget()
        self._telemetry_hooks = []
    
    def add_telemetry_hook(self, hook: Callable[[StageResult], None]):
        """Add a hook that receives each stage result (for tracing)."""
        self._telemetry_hooks.append(hook)
    
    async def process(self, initial_state: ProcessingState) -> ProcessingState:
        """Run the pipeline, stopping early if any stage interrupts or budget exceeded."""
        state = initial_state
        start_time = asyncio.get_event_loop().time()
        
        for stage in self.stages:
            # Check global budget before each stage
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            if self.budget.is_exhausted(state.recursion_depth, elapsed_ms):
                logger.warning(f"Cognitive budget exhausted before stage {stage.name}")
                break
            
            result = await stage.execute(state)
            state = result.state
            
            # Notify telemetry
            for hook in self._telemetry_hooks:
                try:
                    hook(result)
                except Exception as e:
                    logger.error(f"Telemetry hook failed: {e}")
            
            if result.interrupted:
                logger.info(f"Pipeline interrupted at stage {stage.name}")
                break
        
        return state
    
    @classmethod
    def from_stage_functions(cls, stage_funcs: List[tuple], budget: Optional[CognitiveBudget] = None):
        """Helper: each tuple is (name, async_func, timeout_ms)."""
        stages = [PipelineStage(name, func, timeout) for (name, func, timeout) in stage_funcs]
        return cls(stages, budget)

# Alias for import compatibility
ProcessingPipeline = CognitivePipeline
