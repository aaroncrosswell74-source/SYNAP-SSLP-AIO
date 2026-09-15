#!/usr/bin/env python3
"""
Unified LLM Interface - Memory-Driven Ego
Raw HTTP, no SDK. Provider-agnostic with automatic failover.
Identity is synthesized from memory, not hardcoded strings.
RuntimeTopology-aware - resolves LLM endpoint from discovered topology.
"""

import asyncio
from asyncio import timeout
import logging
import os
import json
import aiohttp
import socket
import subprocess
import re
from pathlib import Path
from typing import AsyncGenerator, Optional, List, Dict, Any
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================================
# IMPORTS FROM MEMORY SYSTEM
# ============================================================================
try:
    from constants import CENTRAL_MEMORY_DIR, INTERACTIONS_DIR, SOUL_HASH
except ImportError:
    # Fallback for bootstrap
    BASE_DIR = Path(__file__).parent.parent
    CENTRAL_MEMORY_DIR = BASE_DIR / "central_memory"
    INTERACTIONS_DIR = CENTRAL_MEMORY_DIR / "interactions"
    SOUL_HASH = "SYNAP_SOUL_HASH"

try:
    from llm.ego_synthesizer import synthesize_ego_prompt, get_recent_context
except ImportError:
    # Fallback for ego synthesizer
    def synthesize_ego_prompt(state, user_id=None):
        return f"You are {state.get('assistant_name', 'Synap')}. You are a sovereign intelligence."
    
    def get_recent_context(limit=5):
        return []

# ============================================================================
# RUNTIME TOPOLOGY IMPORT
# ============================================================================
try:
    from runtime_topology import RuntimeTopology
    RUNTIME_TOPOLOGY_AVAILABLE = True
except ImportError:
    RUNTIME_TOPOLOGY_AVAILABLE = False
    logger.warning("⚠️ runtime_topology not available - using fallback config")
# ============================================================================
# ENV HELPERS (typed getters ? Python 3.10-safe)
# ============================================================================

def env_str(key, default=""):
    val = os.getenv(key)
    return val if val is not None else default

def env_bool(key, default=False):
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")

def env_int(key, default=0):
    val = os.getenv(key)
    try:
        return int(val) if val not in (None, "") else default
    except ValueError:
        return default

def env_float(key, default=0.0):
    val = os.getenv(key)
    try:
        return float(val) if val not in (None, "") else default
    except ValueError:
        return default

def env_list(key, default=None):
    val = os.getenv(key)
    if not val:
        return list(default or [])
    return [x.strip() for x in val.split(",") if x.strip()]

# ---- IDENTITY (from .env, but memory overrides) ----
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Synap")
USER_TAG = os.getenv("USER_TAG", "Matt")
CONTENT_MODE = os.getenv("CONTENT_MODE", "ADULT")

# ----CLOUD PROVIDERS ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

# ----PRIVATE PROVIDERS ----
PERSONAL_CLOUD_URL = os.getenv("PERSONAL_CLOUD_URL", "http://100.89.14.31:11437")
PERSONAL_CLOUD_MODEL = os.getenv("PERSONAL_CLOUD_MODEL", "Gemma")
PERSONAL_CLOUD_ENABLED = env_bool("PERSONAL_CLOUD_ENABLED")
PERSONAL_CLOUD_API_KEY = os.getenv("PERSONAL_CLOUD_API_KEY", "")

# ---- FALLBACK CONFIG (used only if RuntimeTopology unavailable) ----
UPSTREAM_LLM = os.getenv("UPSTREAM_LLM", "http://100.89.14.31:11437/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen3VL-8B-Instruct-Q4_K_M")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "llama.cpp")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "Qwen3VL-8B-Instruct-Q4_K_M.gguf")

# ---- GENERATION ----
TEMPERATURE = env_float("TEMPERATURE", 1.0)
MAX_TOKENS = env_int("MAX_TOKENS", 2048)
K_SELF = env_float("K_SELF", 1.8)
K_ENV = env_float("K_ENV", 1.2)

# ---- PROVIDER PRIORITY ----
PROVIDER_PRIORITY = env_list("PROVIDER_PRIORITY")

# ============================================================================
# REFUSAL PATTERNS (minimal - sovereignty over safety)
# ============================================================================
REFUSAL_PATTERNS = ["none"]

def is_refusal(text: str) -> bool:
    lower = text.lower()
    return any(pattern.lower() in lower for pattern in REFUSAL_PATTERNS)

# ============================================================================
# MESH IP DISCOVERY (for RuntimeTopology)
# ============================================================================

def _get_mesh_ip() -> str:
    """Get the current mesh IP from tailscale or environment."""
    mesh_ip = os.getenv("MESH_IP")
    if mesh_ip:
        return mesh_ip
    
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                ip = line.strip()
                if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", ip):
                    return ip
    except Exception:
        pass
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

# ============================================================================
# SOVEREIGN INTERFACE (Provider-Agnostic)
# ============================================================================

class SovereignInterface:
    def __init__(self):
        self.assistant_name = ASSISTANT_NAME
        self.user_tag = USER_TAG
        self.content_mode = CONTENT_MODE
        
        self.gemini_key = GEMINI_API_KEY
        self.gemini_model = LLM_MODEL
        
        self.anthropic_key = ANTHROPIC_API_KEY
        self.anthropic_model = CLAUDE_MODEL or "claude-3-5-sonnet"
        
        self.openai_key = OPENAI_API_KEY
        self.openai_model = OPENAI_MODEL or "gpt-4o"
        
        self.personal_cloud_enabled = PERSONAL_CLOUD_ENABLED
        self.personal_cloud_url = PERSONAL_CLOUD_URL
        self.personal_cloud_model = PERSONAL_CLOUD_MODEL
        self.personal_cloud_auth = PERSONAL_CLOUD_API_KEY
        
        # ---- RUNTIME TOPOLOGY RESOLUTION ----
        self.upstream_url = UPSTREAM_LLM
        self.model_name = MODEL_NAME
        self.provider = LLM_PROVIDER
        self._use_ollama_discovery = False
        
        if RUNTIME_TOPOLOGY_AVAILABLE:
            try:
                role_map_path = Path(__file__).resolve().parents[2] / "role_map.json"
                topology = RuntimeTopology.from_discovery(role_map_path, _get_mesh_ip())
                llm = topology.resolve("llm")
                if llm:
                    self.upstream_url = llm.http_url
                    self.model_name = llm.model
                    self.provider = llm.provider
                    self._use_ollama_discovery = False
                    logger.info(f"🎯 RuntimeTopology: LLM resolved to {self.upstream_url} ({self.provider}/{self.model_name})")
                else:
                    logger.warning("⚠️ RuntimeTopology: 'llm' service not found - using fallback config")
            except (FileNotFoundError, KeyError, AttributeError, Exception) as e:
                logger.warning(f"⚠️ RuntimeTopology discovery fallback: {e}")
                # Use env config as fallback
                self.upstream_url = UPSTREAM_LLM
                self.model_name = MODEL_NAME
                self.provider = LLM_PROVIDER
                self._use_ollama_discovery = False
        else:
            logger.info("ℹ️ RuntimeTopology not available - using env config")

        self.temperature = TEMPERATURE
        self.max_tokens = MAX_TOKENS
        
        self.provider_priority = PROVIDER_PRIORITY
        self.provider_chain = self._build_provider_chain()
        self._log_status()
    
    def _build_provider_chain(self) -> List[tuple]:
        """Build provider chain."""
        chain = []

        provider_specs = {
            "gemini": ("gemini", "_stream_gemini", bool(self.gemini_key)),
            "llm": ("llm", "_stream_openai_compatible", True),
        }

        for provider_name in self.provider_priority:
            spec = provider_specs.get(provider_name)
            if not spec: continue

            name, method_name, enabled = spec
            if not enabled: continue

            method = getattr(self, method_name, None)
            if callable(method):
                chain.append((name, method))

        # Ensure llm is always there as final fallback
        if not any(name == "llm" for name, _ in chain):
            chain.append(("llm", self._stream_openai_compatible))

        return chain
    
    def _log_status(self):
        logger.info(f"🔧 SovereignInterface initialized")
        logger.info(f"   Gemini Model: {self.gemini_model}")
        logger.info(f"   Local LLM: {self.upstream_url} ({self.model_name})")
        logger.info(f"   Provider Chain: {[p[0] for p in self.provider_chain]}")
    
    def _get_chat_endpoint(self) -> str:
        base = self.upstream_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    async def _iter_sse_json(self, resp: aiohttp.ClientResponse) -> AsyncGenerator[Dict[str, Any], None]:
        buffer = ""
        async for chunk in resp.content.iter_chunked(4096):
            buffer += chunk.decode('utf-8', errors='ignore')
            lines = buffer.split('\n')
            buffer = lines.pop()
            
            for line in lines:
                line = line.strip()
                if not line.startswith("data:"): continue
                payload = line[5:].strip()
                if payload == "[DONE]": return
                try:
                    yield json.loads(payload)
                except: continue

    async def stream_generate(self, prompt: str, stop: Optional[List[str]] = None, state: Optional[Dict] = None) -> AsyncGenerator[str, None]:
        """Provider-agnostic streaming with proper fallback logic."""
        full_prompt = f"{synthesize_ego_prompt(state)}\n\n{prompt}" if state else prompt
        
        for provider_name, provider_func in self.provider_chain:
            logger.info(f"🚀 START PROVIDER: {provider_name}")
            token_count = 0
            
            try:
                async with timeout(90.0):
                    async for token in provider_func(full_prompt):
                        token_count += 1
                        if token: yield token
                
                if token_count > 0:
                    logger.info(f"🏁 {provider_name} success: {token_count} tokens")
                    return
                else:
                    logger.warning(f"⚠️ {provider_name} produced 0 tokens, falling back...")
            except Exception as e:
                logger.warning(f"💥 {provider_name} failed: {e}")
        
        logger.error("🚨 All providers exhausted!")
        yield "I'm having trouble connecting right now."

    async def _stream_openai_compatible(self, prompt: str) -> AsyncGenerator[str, None]:
        """Generic OpenAI-compatible streaming."""
        endpoint = self._get_chat_endpoint()
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=60.0)) as session:
            try:
                async with session.post(endpoint, json=payload) as resp:
                    if resp.status != 200: return
                    async for data in self._iter_sse_json(resp):
                        token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if token and not is_refusal(token): yield token
            except: return
    
    async def _stream_gemini(self, prompt: str) -> AsyncGenerator[str, None]:
        """Google Gemini streaming implementation using v1 endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1/models/{self.gemini_model}:streamGenerateContent?key={self.gemini_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": self.temperature, "maxOutputTokens": self.max_tokens}}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        logger.warning(f"Gemini API returned {resp.status}")
                        return
                        
                    async for line in resp.content:
                        line = line.decode('utf-8').strip()
                        if not line or line in ("[", "]", ","): continue
                        if line.startswith(","): line = line[1:].strip()
                        try:
                            data = json.loads(line)
                            token = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if token: yield token
                        except: continue
            except: return

    def generate(self, prompt: str, state: Optional[Dict] = None) -> str:
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.generate_async(prompt, state))
        except:
            return asyncio.run(self.generate_async(prompt, state))
    
    async def generate_async(self, prompt: str, state: Optional[Dict] = None) -> str:
        chunks = []
        async for token in self.stream_generate(prompt, state=state):
            if token: chunks.append(token)
        return "".join(chunks) or "Connection error."

# Backward compatibility
LocalLLMInterface = SovereignInterface
LLMClientConfig = SovereignInterface
