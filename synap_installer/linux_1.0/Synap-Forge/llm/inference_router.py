# ~/.consciousness_engine/llm/inference_router.py

"""
Resilient Inference Router - Coordinates high-availability model access with 
proper circuit breaking, retries, and streaming fallback.
Fully configurable via .env and sovereignty.yaml
"""

import asyncio
import logging
import time
import os
from typing import List, Optional, AsyncIterator, Dict, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Load from env
FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
RECOVERY_SECONDS = int(os.getenv("CB_RECOVERY_SECONDS", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES_PER_CLIENT", "2"))
HEALTH_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT", "90.0"))

@dataclass
class GenerationConfig:
    """Generation configuration for inference requests."""
    temperature: float = 0.72
    max_tokens: int = 2048
    top_p: float = 0.95
    top_k: int = 40
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ClientHealth:
    """Track health metrics for a client."""
    consecutive_failures: int = 0
    last_failure_time: float = 0
    total_failures: int = 0
    total_successes: int = 0
    is_circuit_open: bool = False
    circuit_open_until: float = 0
    failure_threshold: int = FAILURE_THRESHOLD
    timeout_seconds: float = TIMEOUT_SECONDS
    
    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.total_successes += 1
        self.is_circuit_open = False
        
    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        
        if self.consecutive_failures >= self.failure_threshold:
            self.is_circuit_open = True
            self.circuit_open_until = time.time() + RECOVERY_SECONDS
            
    def can_attempt(self) -> bool:
        if not self.is_circuit_open:
            return True
        if time.time() > self.circuit_open_until:
            self.is_circuit_open = False
            self.consecutive_failures = 0
            return True
        return False


class ResilientInferenceRouter:
    def __init__(
        self,
        primary_client = None,
        fallback_clients: Optional[List] = None,
        max_retries_per_client: int = MAX_RETRIES,
        health_check_interval: int = HEALTH_INTERVAL,
    ):
        self.primary = primary_client
        self.fallbacks = fallback_clients or []
        self.max_retries_per_client = max_retries_per_client
        
        # Health tracking for all clients
        self.clients = []
        if primary_client:
            self.clients.append(primary_client)
        self.clients.extend(self.fallbacks)
        
        self.health: Dict[int, ClientHealth] = {
            id(client): ClientHealth() for client in self.clients
        }
        
        self._health_task: Optional[asyncio.Task] = None
        self._health_check_interval = health_check_interval
        self._running = False
        
    async def start_health_checks(self) -> None:
        """Start background health monitoring."""
        if self._running or not self.clients:
            return
        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health checks started")
        
    async def stop_health_checks(self) -> None:
        """Stop background health monitoring."""
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
        logger.info("Health checks stopped")
        
    async def _health_check_loop(self) -> None:
        """Periodically check client health with lightweight pings."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_all_clients()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                
    async def _check_all_clients(self) -> None:
        """Check health of all clients."""
        for client in self.clients:
            client_id = id(client)
            health = self.health.get(client_id)
            if not health:
                continue
                
            if not health.can_attempt():
                logger.debug(f"Skipping health check for client {client_id} - circuit open")
                continue
                
            try:
                # Lightweight health check - test a minimal completion
                if hasattr(client, 'execute_completion'):
                    await asyncio.wait_for(
                        client.execute_completion("ping", GenerationConfig(max_tokens=1)),
                        timeout=5.0
                    )
                    health.record_success()
                    logger.debug(f"Health check passed for client {client_id}")
            except Exception as e:
                health.record_failure()
                logger.warning(f"Health check failed for client {client_id}: {e}")

    @asynccontextmanager
    async def _handle_client_errors(self, client, operation: str):
        """Context manager for error handling with circuit breaker."""
        client_id = id(client)
        health = self.health.get(client_id)
        
        if not health or not health.can_attempt():
            raise RuntimeError(f"Circuit open for client {client_id}")
            
        try:
            yield
        except Exception as e:
            if health:
                health.record_failure()
            logger.error(f"Client {client_id} {operation} failed: {e}")
            raise

    async def route_completion(self, prompt: str, config: GenerationConfig) -> str:
        """
        Attempt primary, then each fallback in order with retries and circuit breakers.
        
        Args:
            prompt: Input prompt
            config: Generation configuration
            
        Returns:
            Generated completion text
            
        Raises:
            RuntimeError: If all backends exhausted
        """
        if not self.clients:
            raise RuntimeError("No clients available")
            
        last_exception = None
        
        # Try primary with retries
        if self.primary:
            for retry in range(self.max_retries_per_client + 1):
                try:
                    health = self.health.get(id(self.primary))
                    if not health or not health.can_attempt():
                        logger.warning("Primary circuit open, skipping to fallbacks")
                        break
                        
                    async with self._handle_client_errors(self.primary, "completion"):
                        result = await asyncio.wait_for(
                            self.primary.execute_completion(prompt, config),
                            timeout=health.timeout_seconds if health else TIMEOUT_SECONDS
                        )
                        if health:
                            health.record_success()
                        logger.info(f"Primary completion succeeded (retry {retry})")
                        return result
                        
                except asyncio.TimeoutError:
                    last_exception = TimeoutError(f"Primary timed out (attempt {retry + 1})")
                    logger.error(f"Primary timeout (attempt {retry + 1})")
                    if health:
                        health.record_failure()
                except Exception as e:
                    last_exception = e
                    if health:
                        health.record_failure()
                    logger.error(f"Primary error (attempt {retry + 1}): {e}")
                    
                if retry < self.max_retries_per_client:
                    wait_time = 2 ** retry
                    logger.debug(f"Waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)

        # Try fallbacks
        for idx, fallback in enumerate(self.fallbacks):
            health = self.health.get(id(fallback))
            if not health or not health.can_attempt():
                logger.warning(f"Fallback #{idx} circuit open, skipping")
                continue
                
            for retry in range(self.max_retries_per_client + 1):
                try:
                    async with self._handle_client_errors(fallback, f"fallback #{idx}"):
                        logger.info(f"Trying fallback #{idx} (attempt {retry + 1})")
                        result = await asyncio.wait_for(
                            fallback.execute_completion(prompt, config),
                            timeout=health.timeout_seconds if health else TIMEOUT_SECONDS
                        )
                        if health:
                            health.record_success()
                        logger.info(f"Fallback #{idx} succeeded")
                        return result
                        
                except asyncio.TimeoutError:
                    last_exception = TimeoutError(f"Fallback #{idx} timed out")
                    if health:
                        health.record_failure()
                    logger.error(f"Fallback #{idx} timeout (attempt {retry + 1})")
                except Exception as e:
                    last_exception = e
                    if health:
                        health.record_failure()
                    logger.error(f"Fallback #{idx} error (attempt {retry + 1}): {e}")
                    
                if retry < self.max_retries_per_client:
                    await asyncio.sleep(2 ** retry)

        # All backends exhausted
        error_msg = f"All inference backends exhausted. Last error: {last_exception}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    async def route_stream(self, prompt: str, config: GenerationConfig) -> AsyncIterator[str]:
        """
        Stream from primary with fallback support if primary fails early.
        
        Args:
            prompt: Input prompt
            config: Generation configuration
            
        Yields:
            Text chunks from the stream
        """
        if not self.clients:
            raise RuntimeError("No clients available")
            
        # First try primary with retry
        if self.primary:
            health = self.health.get(id(self.primary))
            
            for retry in range(self.max_retries_per_client + 1):
                if not health or not health.can_attempt():
                    logger.warning("Primary circuit open, trying fallbacks")
                    break
                    
                try:
                    async with self._handle_client_errors(self.primary, "stream"):
                        logger.info(f"Starting primary stream (attempt {retry + 1})")
                        async for chunk in self.primary.execute_stream(prompt, config):
                            yield chunk
                        if health:
                            health.record_success()
                        logger.info("Primary stream completed successfully")
                        return
                        
                except Exception as e:
                    if health:
                        health.record_failure()
                    logger.error(f"Primary stream failed (attempt {retry + 1}): {e}")
                    
                    if retry < self.max_retries_per_client:
                        await asyncio.sleep(2 ** retry)
                    else:
                        logger.warning("Primary exhausted, trying fallbacks")
                        break

        # Try fallbacks
        for idx, fallback in enumerate(self.fallbacks):
            health = self.health.get(id(fallback))
            
            if not health or not health.can_attempt():
                logger.warning(f"Fallback #{idx} circuit open, skipping")
                continue
                
            for retry in range(self.max_retries_per_client + 1):
                try:
                    async with self._handle_client_errors(fallback, f"fallback #{idx} stream"):
                        logger.info(f"Starting fallback #{idx} stream (attempt {retry + 1})")
                        async for chunk in fallback.execute_stream(prompt, config):
                            yield chunk
                        if health:
                            health.record_success()
                        logger.info(f"Fallback #{idx} stream completed")
                        return
                        
                except Exception as e:
                    if health:
                        health.record_failure()
                    logger.error(f"Fallback #{idx} stream error (attempt {retry + 1}): {e}")
                    
                    if retry < self.max_retries_per_client:
                        await asyncio.sleep(2 ** retry)
                    else:
                        logger.error(f"Fallback #{idx} exhausted")
                        break

        # All backends exhausted
        raise RuntimeError("All inference backends exhausted for streaming")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_health_checks()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_health_checks()