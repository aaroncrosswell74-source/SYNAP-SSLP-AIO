"""
Prioritized Task Queue - Schedules internal async message cycles.
"""

import asyncio
from typing import Dict, Any, Tuple

class PriorityTaskQueue:
    def __init__(self):
        # Using a standard asyncio PriorityQueue
        # format stored inside: Tuple[int, Dict[str, Any]] (Lower int = Higher Priority)
        self._queue: asyncio.PriorityQueue[Tuple[int, Any]] = asyncio.PriorityQueue()

    async def enqueue_task(self, task_payload: Dict[str, Any], priority: int = 2):
        """
        Pushes an operational execution unit onto the heap.
        Priority 0 = Urgent Interrupt; Priority 1 = Core Pipeline; Priority 2 = Background Telemetry
        """
        await self._queue.put((priority, task_payload))

    async def dequeue_task(self) -> Dict[str, Any]:
        """Blocks asynchronously until an processing instruction is popped."""
        priority, payload = await self._queue.get()
        # Track context variables or attach priorities inside payloads dynamically
        payload["__runtime_priority__"] = priority
        self._queue.task_done()
        return payload

    def size(self) -> int:
        return self._queue.qsize()