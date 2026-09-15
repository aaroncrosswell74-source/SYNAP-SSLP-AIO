"""
Execution Context - manages async task lifecycles, cancellation, and graceful shutdown.
"""

import asyncio
import logging
from typing import Set, Coroutine, Any, Optional

logger = logging.getLogger(__name__)


class ExecutionContext:
    """
    Central async execution controller.
    Prevents orphaned tasks and runaway reflections.
    """

    def __init__(self):
        self._tasks: Set[asyncio.Task] = set()
        self._shutdown_requested = False

    async def spawn(self, coro: Coroutine[Any, Any, Any], name: Optional[str] = None) -> asyncio.Task:
        """
        Spawn a new background task and track it.
        Returns the task object.
        """
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def cancel_all(self) -> None:
        """Cancel all tracked tasks and wait for them to complete."""
        if not self._tasks:
            return
        logger.info(f"Cancelling {len(self._tasks)} tracked tasks")
        for task in self._tasks:
            task.cancel()
        # Wait for all cancellations to settle
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def graceful_shutdown(self, timeout_seconds: float = 5.0) -> None:
        """Request graceful shutdown, cancel all tasks, and wait for timeout."""
        self._shutdown_requested = True
        await self.cancel_all()
        # Additional cleanup hooks can be added here
        logger.info("Graceful shutdown complete")

    def is_shutdown_requested(self) -> bool:
        """Return True if a shutdown has been triggered."""
        return self._shutdown_requested


class HardenedExecutionSupervisor:
    """
    Wraps coroutine execution with timeout and fallback protection.
    """

    def __init__(self, critical_timeout_seconds: float = 5.0):
        self.timeout = critical_timeout_seconds

    async def execute_transactional_step(
        self,
        task_id: str,
        coro,
        state_fallback: dict
    ) -> dict:
        """Execute a coroutine with timeout and fallback on failure."""
        import asyncio
        import logging
        logger = logging.getLogger(__name__)
        try:
            result = await asyncio.wait_for(coro, timeout=self.timeout)
            if isinstance(result, dict):
                return result
            # Wrap non-dict results
            return {"status": "completed", "final_text": str(result)}
        except asyncio.TimeoutError:
            logger.error(f"[{task_id}] Execution timed out after {self.timeout}s")
            fallback = dict(state_fallback)
            fallback["error"] = f"Timeout after {self.timeout}s"
            return fallback
        except Exception as e:
            logger.error(f"[{task_id}] Execution failed: {e}")
            fallback = dict(state_fallback)
            fallback["error"] = str(e)
            return fallback
