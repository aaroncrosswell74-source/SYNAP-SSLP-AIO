# router_modes.py
"""
Dual-Mode Inference Router - Supports both public API and Personal Cloud modes.
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RouterMode(Enum):
    """Operating modes for the inference router."""
    PUBLIC = "public"          # Use your hosted APIs (Gemini/Anthropic/OpenAI)
    PERSONAL_CLOUD = "personal"  # User becomes their own 3rd party provider
    HYBRID = "hybrid"          # Primary: personal, fallback: public


@dataclass
class PersonalCloudConfig:
    """Configuration for personal cloud mode."""
    enabled: bool = False
    # The user's personal endpoint that YOU provide
    personal_endpoint: str = "https://api.yourplatform.com/v1/personal"
    # User's auth token for your personal cloud service
    personal_api_key: str = ""
    # Which models they want to serve from their personal cloud
    personal_models: List[str] = field(default_factory=lambda: ["personal-llm"])
    # Fallback to public APIs if personal cloud fails
    fallback_to_public: bool = True
    # Health check endpoint for their personal cloud
    health_check_endpoint: str = "/health"
    

class DualModeResilientRouter:
    """
    Router that can switch between public APIs and personal cloud mode.
    Users pay $19.99 to become their own 3rd party provider through your platform.
    """
    
    def __init__(
        self,
        public_clients: Dict[str, LLMClientInterface],  # Gemini, Anthropic, OpenAI
        personal_cloud_config: Optional[PersonalCloudConfig] = None,
        mode: RouterMode = RouterMode.PUBLIC,
    ):
        self.public_clients = public_clients
        self.personal_config = personal_cloud_config or PersonalCloudConfig()
        self.mode = mode
        
        # Health tracking for both modes
        self.health: Dict[str, ClientHealth] = {}
        self._personal_cloud_healthy = False
        self._last_personal_check = 0
        
    async def route_completion(self, prompt: str, config: GenerationConfig) -> str:
        """Route based on current mode."""
        
        if self.mode == RouterMode.PUBLIC:
            return await self._route_public(prompt, config)
            
        elif self.mode == RouterMode.PERSONAL_CLOUD:
            return await self._route_personal_cloud(prompt, config)
            
        elif self.mode == RouterMode.HYBRID:
            return await self._route_hybrid(prompt, config)
            
    async def _route_public(self, prompt: str, config: GenerationConfig) -> str:
        """Standard public API routing."""
        # Try primary (Gemini), then fallbacks (Anthropic, OpenAI)
        for client_name, client in self.public_clients.items():
            try:
                result = await client.execute_completion(prompt, config)
                logger.info(f"Public API {client_name} succeeded")
                return result
            except Exception as e:
                logger.warning(f"Public API {client_name} failed: {e}")
                continue
        raise RuntimeError("All public APIs exhausted")
        
    async def _route_personal_cloud(self, prompt: str, config: GenerationConfig) -> str:
        """Route through user's personal cloud."""
        
        if not self.personal_config.enabled:
            raise RuntimeError("Personal cloud not enabled")
            
        # Check if personal cloud is healthy
        if not await self._check_personal_cloud_health():
            if self.personal_config.fallback_to_public:
                logger.warning("Personal cloud unhealthy, falling back to public")
                return await self._route_public(prompt, config)
            else:
                raise RuntimeError("Personal cloud unavailable and no fallback")
                
        # Route to personal cloud
        try:
            # This is where YOUR platform acts as the intermediary
            # User pays you $19.99, you give them this endpoint
            result = await self._call_personal_cloud(prompt, config)
            logger.info("Personal cloud succeeded")
            return result
        except Exception as e:
            logger.error(f"Personal cloud failed: {e}")
            if self.personal_config.fallback_to_public:
                logger.info("Falling back to public APIs")
                return await self._route_public(prompt, config)
            raise
            
    async def _route_hybrid(self, prompt: str, config: GenerationConfig) -> str:
        """Try personal cloud first, fallback to public."""
        try:
            return await self._route_personal_cloud(prompt, config)
        except Exception:
            logger.info("Hybrid mode: falling back to public")
            return await self._route_public(prompt, config)
            
    async def _check_personal_cloud_health(self) -> bool:
        """Check if user's personal cloud is healthy."""
        # Rate limit checks to avoid hammering
        if time.time() - self._last_personal_check < 30:
            return self._personal_cloud_healthy
            
        try:
            # Your platform checks the user's personal endpoint
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.personal_config.personal_endpoint}{self.personal_config.health_check_endpoint}",
                    timeout=5.0
                ) as resp:
                    self._personal_cloud_healthy = resp.status == 200
                    self._last_personal_check = time.time()
                    return self._personal_cloud_healthy
        except Exception:
            self._personal_cloud_healthy = False
            self._last_personal_check = time.time()
            return False
            
    async def _call_personal_cloud(self, prompt: str, config: GenerationConfig) -> str:
        """Call the user's personal cloud endpoint."""
        # This is where YOUR platform monetizes
        # You charge $19.99 to give users this capability
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.personal_config.personal_endpoint}/completion",
                headers={
                    "Authorization": f"Bearer {self.personal_config.personal_api_key}",
                    "X-Personal-Cloud": "true"
                },
                json={
                    "prompt": prompt,
                    "config": config.__dict__,
                    "user_id": "personal_cloud_user"  # Track for billing
                },
                timeout=config.timeout or 120.0
            ) as resp:
                data = await resp.json()
                return data["completion"]
