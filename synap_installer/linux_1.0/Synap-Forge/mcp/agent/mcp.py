import json
"""MCP Gateway client with circuit breaker"""

import requests
import logging
import time
from typing import Dict, Any
from .tools import Tool
from .context import get_request_id
from .config import MCP_URL, MAX_TOOL_OUTPUT_SIZE
from .circuit import get_circuit_breaker
from .audit import log_audit_event, hash_arguments

logger = logging.getLogger("MCPClient")

def call_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool via the MCP gateway with circuit breaker"""
    request_id = get_request_id()
    start_time = time.time()
    circuit = get_circuit_breaker()
    
    # Check circuit breaker
    if not circuit.is_allowed(tool.name):
        logger.warning(f"[{request_id}] Circuit breaker open for {tool.name}")
        return {"success": False, "error": f"Circuit breaker open for {tool.name}"}
    
    url = f"{MCP_URL}{tool.endpoint}"
    args_hash = hash_arguments(params)
    
    try:
        logger.info(f"[{request_id}] Calling tool {tool.name} -> {url}")
        resp = requests.post(
            url,
            json={"params": params},
            timeout=tool.timeout
        )
        duration_ms = (time.time() - start_time) * 1000
        
        if resp.status_code != 200:
            circuit.record_failure(tool.name)
            log_audit_event(
                event_type="tool_call",
                tool_name=tool.name,
                arguments_hash=args_hash,
                status="error",
                duration_ms=duration_ms,
                error=f"HTTP {resp.status_code}"
            )
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        
        result = resp.json()
        circuit.record_success(tool.name)
        
        log_audit_event(
            event_type="tool_call",
            tool_name=tool.name,
            arguments_hash=args_hash,
            status="success",
            duration_ms=duration_ms
        )
        
        logger.info(f"[{request_id}] Tool {tool.name} completed in {duration_ms:.0f}ms")
        
        # Cap output size
        if "result" in result and isinstance(result["result"], dict):
            output_size = len(json.dumps(result["result"]))
            if output_size > MAX_TOOL_OUTPUT_SIZE:
                logger.warning(f"[{request_id}] Tool {tool.name} output exceeds limit ({output_size} > {MAX_TOOL_OUTPUT_SIZE})")
        
        # Normalize gateway response
        if "result" not in result:
            result = {
                "success": result.get("success", False),
                "result": {
                    k: v for k, v in result.items()
                    if k not in ("success", "status", "id", "_ms", "error")
                },
                "error": result.get("error")
            }
        
        return result
    except requests.exceptions.Timeout:
        duration_ms = (time.time() - start_time) * 1000
        circuit.record_failure(tool.name)
        log_audit_event(
            event_type="tool_call",
            tool_name=tool.name,
            arguments_hash=args_hash,
            status="timeout",
            duration_ms=duration_ms
        )
        return {"success": False, "error": f"Tool timed out after {tool.timeout}s"}
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        circuit.record_failure(tool.name)
        log_audit_event(
            event_type="tool_call",
            tool_name=tool.name,
            arguments_hash=args_hash,
            status="error",
            duration_ms=duration_ms,
            error=str(e)
        )
        return {"success": False, "error": str(e)}
    except requests.exceptions.Timeout:
        duration_ms = (time.time() - start_time) * 1000
        circuit.record_failure(tool.name)
        log_audit_event(
            event_type="tool_call",
            tool_name=tool.name,
            arguments_hash=args_hash,
            status="timeout",
            duration_ms=duration_ms
        )
        return {"success": False, "error": f"Tool timed out after {tool.timeout}s"}
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        circuit.record_failure(tool.name)
        log_audit_event(
            event_type="tool_call",
            tool_name=tool.name,
            arguments_hash=args_hash,
            status="error",
            duration_ms=duration_ms,
            error=str(e)
        )
        return {"success": False, "error": str(e)}

def execute_tool(name: str, params: Dict[str, Any]) -> tuple[bool, str, Dict]:
    """Execute a tool by name via the MCP gateway"""
    from .tools import get_tool
    
    tool = get_tool(name)
    
    if not tool:
        return False, f"Unknown tool: {name}", {}
    
    if not tool.enabled:
        return False, f"Tool {name} is disabled", {}
    
    valid, error = tool.validate_params(params)
    if not valid:
        return False, error, {}
    
    result = call_tool(tool, params)
    
    return (
        result.get("success", False),
        result.get("error", ""),
        result.get("result", {})
    )