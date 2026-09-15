#!/usr/bin/env python3
"""
circadian_rhythm.py - Scheduler for low-cost processing windows
Handles 1am-5am batch processing and operational rhythms
"""

import asyncio
import logging
import time
import os
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import Redis for distributed locking
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - using file-based locking fallback")


@dataclass
class RhythmState:
    """Current circadian state"""
    phase: str = "AWAKE"  # AWAKE, DROWSY, DEEP_PROCESS, RECOVERY
    last_change: float = field(default_factory=time.time)
    low_cost_window: bool = False
    consolidation_run: bool = False  # Track if already run this window


class CircadianRhythm:
    """
    Manages operational timing rhythms.
    Low-cost window: 1am - 5am daily for batch processing.
    """

    # 1am to 5am - when API costs are lowest
    LOW_COST_START_HOUR = 1
    LOW_COST_END_HOUR = 5

    def __init__(self, enable_consolidation: bool = True):
        self.state = RhythmState()
        self._listeners: Dict[str, List[Callable]] = {
            "window_open": [],
            "window_close": [],
            "phase_change": [],
            "consolidation_start": [],
            "consolidation_end": []
        }
        self.enable_consolidation = enable_consolidation
        self._consolidation_lock_acquired = False
        self._update_phase()
        
        # Redis lock key
        self.lock_key = "circadian:consolidation:lock"
        self.redis_client = None
        if REDIS_AVAILABLE and enable_consolidation:
            try:
                self.redis_client = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis lock available for consolidation")
            except:
                self.redis_client = None
                logger.warning("Redis connection failed - using file lock fallback")

    def get_state(self) -> str:
        """Return current circadian phase"""
        self._update_phase()
        return self.state.phase

    def is_low_cost_window(self) -> bool:
        """Check if currently in 1am-5am low-cost processing window"""
        hour = datetime.now().hour
        return self.LOW_COST_START_HOUR <= hour < self.LOW_COST_END_HOUR

    def _acquire_lock(self) -> bool:
        """
        Acquire distributed lock for consolidation.
        Returns True if lock acquired, False if already locked.
        """
        if not self.enable_consolidation:
            return False
            
        if self.redis_client:
            # Redis lock with 2 hour expiry (covers full window)
            acquired = self.redis_client.setnx(self.lock_key, time.time())
            if acquired:
                self.redis_client.expire(self.lock_key, 7200)  # 2 hours
                logger.info("Redis consolidation lock acquired")
                return True
            else:
                logger.debug("Redis consolidation lock already held")
                return False
        else:
            # File-based fallback lock
            lock_file = "/tmp/circadian_consolidation.lock"
            if os.path.exists(lock_file):
                # Check if lock is stale (> 2 hours old)
                mtime = os.path.getmtime(lock_file)
                if time.time() - mtime > 7200:
                    os.remove(lock_file)
                    logger.info("Stale file lock removed")
                else:
                    return False
            
            # Create lock
            with open(lock_file, 'w') as f:
                f.write(str(time.time()))
            return True

    def _release_lock(self):
        """Release the consolidation lock"""
        if self.redis_client:
            self.redis_client.delete(self.lock_key)
            logger.info("Redis consolidation lock released")
        else:
            lock_file = "/tmp/circadian_consolidation.lock"
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("File lock released")

    def _check_system_load(self) -> bool:
        """
        Check if system is idle enough for consolidation.
        Returns True if safe to run.
        """
        try:
            # Check CPU load average (1 minute)
            load_avg = os.getloadavg()[0]
            if load_avg > 2.0:
                logger.info(f"System load too high ({load_avg:.1f}) - skipping consolidation")
                return False
            
            # Check memory pressure (optional)
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent > 85:
                logger.info(f"Memory pressure too high ({mem.percent}%) - skipping consolidation")
                return False
        except ImportError:
            # psutil not installed - skip memory check
            pass
        except Exception as e:
            logger.warning(f"Load check failed: {e}")
        
        return True

    async def _run_consolidation(self):
        """
        Execute the nightly recursive learning consolidation.
        This is the hook that calls your NightlyRecursiveLearner.
        """
        if not self.enable_consolidation:
            return
        
        # Prevent double-run in same window
        if self.state.consolidation_run:
            logger.debug("Consolidation already run this window")
            return
        
        # Acquire distributed lock
        if not self._acquire_lock():
            logger.info("Consolidation already running on another process")
            return
        
        try:
            # Check system load
            if not self._check_system_load():
                logger.info("System not idle enough for consolidation")
                return
            
            logger.info("🌙 Starting Nightly Recursive Consolidation")
            self._trigger("consolidation_start", {"timestamp": datetime.now().isoformat()})
            
            # Import and run the learner
            try:
                from memory.store import MemoryStore
                store = MemoryStore(storage_path="/home/aaron/Synap-Forge/.consciousness_engine/central_memory")
                from loop.recursive_improvement import NightlyRecursiveLearner
                
                # Create learner instance
                learner = NightlyRecursiveLearner(store)
                
                # Run the consolidation (non-blocking, with timeout)
                # Check if learner has run_nightly_cycle or run_consolidation
                if hasattr(learner, 'run_nightly_cycle'):
                    result = await learner.run_nightly_cycle()
                elif hasattr(learner, 'run_consolidation'):
                    result = await learner.run_consolidation()
                else:
                    # Fallback to think_about with a consolidation prompt
                    result = await learner.think_about(
                        "Nightly consolidation cycle. Analyze recent memories and evolve persona.",
                        depth=2
                    )
                
                logger.info(f"✅ Consolidation complete: {result if isinstance(result, dict) else 'success'}")
                
            except ImportError as e:
                logger.error(f"Could not import NightlyRecursiveLearner: {e}")
                logger.info("Falling back to basic memory consolidation...")
                await self._fallback_consolidation()
            except Exception as e:
                logger.error(f"Consolidation failed: {e}")
            
            # Mark as run for this window
            self.state.consolidation_run = True
            self._trigger("consolidation_end", {"timestamp": datetime.now().isoformat()})
            
        finally:
            self._release_lock()

    async def _fallback_consolidation(self):
        """Fallback if recursive_improvement is not available"""
        try:
            from memory.consolidation import MemoryConsolidator
            from memory.store import MemoryStore
            
            store = MemoryStore(storage_path="/home/aaron/Synap-Forge/.consciousness_engine/central_memory")
            consolidator = MemoryConsolidator()
            
            # Get recent memories
            recent = store.get_recent(limit=100)
            if recent:
                consolidated = consolidator.consolidate_batch(recent)
                logger.info(f"Fallback consolidation: {len(consolidated)} memories consolidated")
        except Exception as e:
            logger.error(f"Fallback consolidation failed: {e}")

    def _update_phase(self) -> None:
        """Update phase based on current time"""
        old_phase = self.state.phase
        hour = datetime.now().hour

        if self.is_low_cost_window():
            new_phase = "DEEP_PROCESS"
            if not self.state.low_cost_window:
                self.state.low_cost_window = True
                self.state.consolidation_run = False  # Reset for new window
                self._trigger("window_open", {"hour": hour})
        elif hour < 8 or hour > 22:
            new_phase = "DROWSY"
            self.state.low_cost_window = False
        else:
            new_phase = "AWAKE"
            self.state.low_cost_window = False

        if new_phase != old_phase:
            self.state.phase = new_phase
            self.state.last_change = time.time()
            self._trigger("phase_change", {"from": old_phase, "to": new_phase})

        if not self.is_low_cost_window() and self.state.low_cost_window:
            self.state.low_cost_window = False
            self._trigger("window_close", {"hour": hour})

    def _trigger(self, event: str, data: Dict[str, Any]) -> None:
        """Trigger registered callbacks"""
        for cb in self._listeners.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"Circadian callback error: {e}")

    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for circadian events"""
        if event in self._listeners:
            self._listeners[event].append(callback)

    async def wait_for_window(self) -> None:
        """Async wait until low-cost window opens"""
        while not self.is_low_cost_window():
            now = datetime.now()
            hour = now.hour

            if hour >= self.LOW_COST_END_HOUR:
                seconds_left = (24 - hour + self.LOW_COST_START_HOUR) * 3600
            else:
                seconds_left = (self.LOW_COST_START_HOUR - hour) * 3600
                if seconds_left < 0:
                    seconds_left += 86400

            sleep_time = min(seconds_left, 900)
            await asyncio.sleep(sleep_time)
            self._update_phase()

        logger.info("Low-cost processing window OPEN")

    async def monitor_rhythms(self) -> None:
        """
        Main monitoring loop.
        Runs continuously and triggers consolidation when window opens.
        """
        logger.info("Circadian rhythm monitor started")
        
        while True:
            try:
                if self.is_low_cost_window() and self.enable_consolidation:
                    # Only run if not already run this window
                    if not self.state.consolidation_run:
                        logger.info("Low-cost window active - starting consolidation")
                        await self._run_consolidation()
                    
                    # Wait until window closes before checking again
                    seconds_until_close = self._seconds_until_window_close()
                    if seconds_until_close > 0:
                        await asyncio.sleep(min(seconds_until_close, 300))
                else:
                    # Check every 15 minutes outside window
                    await asyncio.sleep(900)
                    
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(60)

    def _seconds_until_next_window(self) -> int:
        """Calculate seconds until next low-cost window opens"""
        if self.is_low_cost_window():
            return 0

        now = datetime.now()
        hour = now.hour
        minute = now.minute
        second = now.second

        if hour >= self.LOW_COST_END_HOUR:
            hours_left = (24 - hour) + self.LOW_COST_START_HOUR
        else:
            hours_left = self.LOW_COST_START_HOUR - hour

        return hours_left * 3600 - (minute * 60) - second

    def _seconds_until_window_close(self) -> int:
        """Calculate seconds until current low-cost window closes"""
        if not self.is_low_cost_window():
            return 0

        now = datetime.now()
        hour = now.hour
        minute = now.minute
        second = now.second
        
        hours_left = self.LOW_COST_END_HOUR - hour - 1
        minutes_left = 60 - minute
        return max(0, hours_left * 3600 + minutes_left * 60 - second)

    def get_schedule(self) -> Dict[str, Any]:
        """Return scheduling information"""
        self._update_phase()
        return {
            "current_phase": self.state.phase,
            "low_cost_window_active": self.is_low_cost_window(),
            "next_window_starts": self._seconds_until_next_window(),
            "consolidation_run_today": self.state.consolidation_run,
            "low_cost_hours": f"{self.LOW_COST_START_HOUR}:00-{self.LOW_COST_END_HOUR}:00"
        }


# Standalone runner for testing
async def main():
    logging.basicConfig(level=logging.INFO)
    
    rhythm = CircadianRhythm(enable_consolidation=True)
    print("Schedule:", rhythm.get_schedule())
    
    # Run monitor (will trigger consolidation at 1am)
    await rhythm.monitor_rhythms()


if __name__ == "__main__":
    asyncio.run(main())