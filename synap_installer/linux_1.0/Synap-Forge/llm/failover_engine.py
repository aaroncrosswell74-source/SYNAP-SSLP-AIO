# llm/failover_engine.py

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import AsyncGenerator, List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ProviderStatus(Enum):
    """States a provider can be in during failover."""
    IDLE = auto()
    ATTEMPTING = auto()
    STREAMING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()

@dataclass
class ProviderResult:
    """Structured outcome from a provider attempt."""
    tokens_yielded: int = 0
    completed: bool = False
    error: Optional[Exception] = None
    status: ProviderStatus = ProviderStatus.IDLE
    metadata: Dict[str, Any] = field(default_factory=dict)

class FailoverEngine:
    """
    Declarative failover state machine.
    
    Providers are tried in order. First one to yield tokens wins.
    Empty stream = failure. Exception = failure. Move to next.
    """
    
    def __init__(self, providers: List[tuple]):
        """
        Args:
            providers: List of (name, async_generator_function)
        """
        self.providers = providers
        self.results: Dict[str, ProviderResult] = {}
        self._current_provider = None
    
    async def execute(self, prompt: str) -> AsyncGenerator[str, None]:
        """Run the failover state machine."""
        
        for provider_name, provider_func in self.providers:
            self._current_provider = provider_name
            result = ProviderResult(status=ProviderStatus.ATTEMPTING)
            self.results[provider_name] = result
            
            logger.debug(f"🔄 Attempting {provider_name}...")
            
            try:
                async for token in provider_func(prompt):
                    result.tokens_yielded += 1
                    result.status = ProviderStatus.STREAMING
                    
                    # Token-level validation (optional)
                    if token:
                        yield token
                
                # Provider completed successfully
                result.completed = True
                result.status = ProviderStatus.COMPLETED
                
                # Empty stream detection
                if result.tokens_yielded == 0:
                    result.error = ProviderError(f"{provider_name} returned empty stream")
                    result.status = ProviderStatus.FAILED
                    logger.warning(f"❌ {provider_name} failed: empty stream")
                    continue
                
                logger.debug(f"✅ {provider_name} complete ({result.tokens_yielded} tokens)")
                return  # Success - stop chain
                
            except ProviderError as e:
                result.error = e
                result.status = ProviderStatus.FAILED
                logger.warning(f"❌ {provider_name} failed: {e}")
                continue
                
            except Exception as e:
                result.error = e
                result.status = ProviderStatus.FAILED
                logger.warning(f"❌ {provider_name} failed (unexpected): {e}")
                continue
        
        # All providers exhausted
        last_error = self.results.get(self._current_provider, ProviderResult()).error
        raise ProviderError(f"All providers exhausted. Last error: {last_error}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all provider attempts."""
        return {
            name: {
                "status": result.status.name,
                "tokens": result.tokens_yielded,
                "completed": result.completed,
                "error": str(result.error) if result.error else None
            }
            for name, result in self.results.items()
        }

class ProviderError(Exception):
    """Raised when a provider fails and we need to try the next one."""
    pass