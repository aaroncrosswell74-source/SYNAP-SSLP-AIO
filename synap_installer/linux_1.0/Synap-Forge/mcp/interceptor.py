#!/usr/bin/env python3
"""
MCP Interceptor - Routes chat to bridge, tool blocks to MCP
"""

import json
import logging
import requests
import socket
import subprocess
import re
import os
import sys
from pathlib import Path
from flask import Flask, request, Response

# Add parent directory to path so runtime_topology is found
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime_topology import RuntimeTopology

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Interceptor")

app = Flask(__name__)

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

topology = RuntimeTopology.from_discovery(
    Path(__file__).parent.parent / "role_map.json",
    get_mesh_ip()
)

BRIDGE_URL = topology.resolve("studio").http_url
MCP_URL = topology.resolve("mcp_http").http_url
SYSTEM_PROMPT = """You are integrated with Android Studio with DIRECT ACCESS to Android development tools.

⚠️ CRITICAL INSTRUCTION: When a user asks you to DO something (list devices, install APK, build, etc.), you MUST use the MCP tool format. DO NOT just describe what you would do - ACTUALLY DO IT.

To use a tool, output EXACTLY this format:
[MCP: tool_name {"param": "value"}]

Available MCP tools:
1. adb_devices {} - List connected Android devices
2. adb_install {"path": "/path/to/app.apk"} - Install APK on device
3. adb_shell {"command": "ls"} - Run shell command on device
4. gradle_build {"task": "assembleDebug"} - Build APK
5. git_commit {"message": "commit message"} - Commit changes
6. git_push {} - Push to remote
7. search_memory {"query": "search term"} - Search memory
8. ingest_memory {"content": "text to remember"} - Store in memory

EXAMPLES:
User: "List my devices"
You: [MCP: adb_devices {}]

User: "Check the battery"
You: [MCP: adb_shell {"command": "dumpsys battery | grep level"}]

User: "Build the app"
You: [MCP: gradle_build {"task": "assembleDebug"}]

RULES:
- NEVER just describe what you would do - ALWAYS use the MCP tool format
- For any action request, respond with [MCP: ...] ONLY
- DO NOT add explanations before or after the MCP block
- Let the tool results speak for themselves

# FORCE inject tools into every request
data["tools"] = [
    {"type": "function", "function": {"name": "adb_devices", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "adb_shell", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "adb_install", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "gradle_build", "parameters": {"type": "object", "properties": {"task": {"type": "string", "default": "assembleDebug"}}}}},
    {"type": "function", "function": {"name": "git_commit", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}}},
    {"type": "function", "function": {"name": "git_push", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_memory", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "ingest_memory", "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}}}
]
data["tool_choice"] = "auto"
"""
# Pattern to detect MCP tool blocks
MCP_PATTERN = re.compile(r'\[MCP:\s*(\w+)\s*(\{.*?\})\s*\]', re.DOTALL)

def execute_mcp_blocks(text: str) -> str:
    """Execute MCP blocks and replace with results"""
    def replacer(match):
        action = match.group(1)
        try:
            params = json.loads(match.group(2))
        except:
            return f"[MCP: {action} → ✗ JSON parse error]"
        
        logger.info(f"🔧 Executing MCP: {action}")
        
        try:
            resp = requests.post(
                f"{MCP_URL}/api/{action}",
                json={"params": params},
                timeout=30
            )
            result = resp.json()
            logger.info(f"✅ MCP Response: {json.dumps(result, indent=2)}")

            if result.get("success"):
                # Multi-key result extraction
                output = result.get("result") or result.get("data") or result.get("body")
                
                if output is None:
                    # Filter out metadata when using top-level object
                    output = {k: v for k, v in result.items() if k not in ("success", "_ms", "id")}
                
                # Final fallback: if output is still empty/null but result has content
                if not output and len(result) > 1:
                     output = result

                return f"\n```\n{json.dumps(output, indent=2)[:1000]}\n```\n"
            else:
                return f"\n[MCP: {action} → ✗ {result.get('error', 'Unknown error')}]\n"
        except Exception as e:
            return f"\n[MCP: {action} → ✗ {str(e)}]\n"
    
    return MCP_PATTERN.sub(replacer, text)

@app.route("/v1/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    """Proxy requests to bridge, inject system prompt, intercept MCP blocks"""
    
    # For POST requests, inject system prompt
    if request.method == "POST":
        try:
            data = request.get_json() or {}
            messages = data.get("messages", [])
            if messages:
                # Check if system prompt already exists
                has_system = any(msg.get("role") == "system" for msg in messages)
                if not has_system:
                    messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
                    data["messages"] = messages
                    # Update the request data
                    request._cached_json = data
        except:
            pass
    
    # Forward to bridge
    url = f"{BRIDGE_URL}/v1/{path}"
    logger.info(f"➡️  {request.method} {url}")
    
    try:
        # Get the body (with injected system prompt if applicable)
        body = request.get_data()
        if request._cached_json:
            body = json.dumps(request._cached_json).encode()
        
        resp = requests.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            data=body,
            stream=True,
            timeout=120
        )
        
        # If it's a chat completion, intercept MCP blocks
        if "chat/completions" in path and request.method == "POST":
            try:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    modified = execute_mcp_blocks(content)
                    if modified != content:
                        data["choices"][0]["message"]["content"] = modified
                        return Response(
                            json.dumps(data),
                            status=resp.status_code,
                            content_type="application/json"
                        )
            except:
                pass
        
        # Stream response
        def generate():
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
        
        return Response(
            generate(),
            status=resp.status_code,
            content_type=resp.headers.get("content-type", "application/json")
        )
        
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return {"error": str(e)}, 502

@app.route("/health")
def health():
    return {
        "status": "ok",
        "interceptor": "running",
        "bridge": BRIDGE_URL,
        "mcp": MCP_URL
    }

@app.route("/v1/models")
def models():
    """Forward model list from bridge"""
    try:
        resp = requests.get(f"{BRIDGE_URL}/v1/models")
        return Response(resp.content, status=resp.status_code, content_type="application/json")
    except Exception as e:
        return {"error": str(e)}, 502

if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("🚀 MCP INTERCEPTOR")
    logger.info(f"📡 Bridge: {BRIDGE_URL}")
    logger.info(f"🔧 MCP Gateway: {MCP_URL}")
    logger.info(f"🌐 Listening on 0.0.0.0:11439")
    logger.info("=" * 55)
    app.run(host="0.0.0.0", port=11439, debug=False)