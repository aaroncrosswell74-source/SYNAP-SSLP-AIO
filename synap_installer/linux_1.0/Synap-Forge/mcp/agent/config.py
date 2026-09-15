"""Configuration management with environment variables and topology resolution"""

import os
import sys
from pathlib import Path
import logging
import socket
import subprocess
import re

logger = logging.getLogger("Config")


def get_mesh_ip():
    mesh_ip = os.getenv("MESH_IP")
    if mesh_ip:
        return mesh_ip
    try:
        result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", line.strip()):
                    return line.strip()
    except:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"


def resolve_topology():
    try:
        from runtime_topology import RuntimeTopology
        mesh_ip = get_mesh_ip()
        topology_path = Path(__file__).resolve().parents[2] / "role_map.json"
        topology = RuntimeTopology.from_discovery(topology_path, mesh_ip)
        mcp = topology.resolve("mcp_http")
        studio = topology.resolve("studio")
        return mcp.http_url, studio.http_url
    except Exception as e:
        logger.warning(f"Topology resolution failed: {e}, using fallbacks")
        return None, None


_topology_mcp, _topology_studio = resolve_topology()

# Environment variables override topology, fallback to localhost
MCP_URL = os.getenv("MCP_URL", _topology_mcp or "http://127.0.0.1:11440")
TARGET_URL = os.getenv("TARGET_URL", _topology_studio or "http://127.0.0.1:11436/v1")

MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "5"))
LOG_DIR = Path(os.getenv("LOG_DIR", "."))
INTERCEPTOR_PORT = int(os.getenv("INTERCEPTOR_PORT", "11439"))
INTERCEPTOR_HOST = os.getenv("INTERCEPTOR_HOST", "0.0.0.0")

# Security
AUTH_TOKEN = os.getenv("AUTH_TOKEN", None)
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

# Rate limiting
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Tool limits
MAX_TOOL_TIMEOUT = int(os.getenv("MAX_TOOL_TIMEOUT", "30"))
MAX_TOOL_OUTPUT_SIZE = int(os.getenv("MAX_TOOL_OUTPUT_SIZE", "10000"))
MAX_CONCURRENT_TOOLS = int(os.getenv("MAX_CONCURRENT_TOOLS", "3"))
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", "1048576"))

# Circuit breaker
CIRCUIT_BREAKER_FAILURES = int(os.getenv("CIRCUIT_BREAKER_FAILURES", "5"))
CIRCUIT_BREAKER_WINDOW = int(os.getenv("CIRCUIT_BREAKER_WINDOW", "60"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "30"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", None)
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))


def validate_config():
    if REQUIRE_AUTH and not AUTH_TOKEN:
        raise RuntimeError("AUTH_TOKEN required when REQUIRE_AUTH is true")
    if MAX_TOOL_ROUNDS < 1 or MAX_TOOL_ROUNDS > 20:
        raise RuntimeError("MAX_TOOL_ROUNDS must be between 1 and 20")
    if RATE_LIMIT_REQUESTS < 1:
        raise RuntimeError("RATE_LIMIT_REQUESTS must be positive")

    logger.info("✅ Configuration validated successfully")
    logger.info(f"   MCP_URL: {MCP_URL}")
    logger.info(f"   TARGET_URL: {TARGET_URL}")
    logger.info(f"   REQUIRE_AUTH: {REQUIRE_AUTH}")
    logger.info(f"   MAX_TOOL_ROUNDS: {MAX_TOOL_ROUNDS}")
    logger.info(f"   MAX_CONCURRENT_TOOLS: {MAX_CONCURRENT_TOOLS}")
    return True


validate_config()