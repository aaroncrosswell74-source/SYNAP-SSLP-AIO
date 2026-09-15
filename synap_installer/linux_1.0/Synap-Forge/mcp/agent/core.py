"""Agent runtime - main loop with tool execution and native tool support"""

import logging
import time
import copy
import hashlib
import json
import os
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import MAX_TOOL_ROUNDS, LOG_DIR, MAX_CONCURRENT_TOOLS
from .tools import TOOLS, get_openai_tools, get_tool, TOOL_POLICY
from .mcp import execute_tool
from .model import call_model
from .parser import MCPParser, parse_block
from .prompt import build_system_prompt
from .types import ToolInvocation, ToolResult, AgentRound, generate_call_id
from .context import get_request_id
from .idempotency import get_idempotency_store
from .audit import log_audit_event, hash_arguments

logger = logging.getLogger("Agent")
STRUCTURED_LOG_FILE = LOG_DIR / "agent_rounds.jsonl"

# Graceful shutdown
def setup_signal_handlers():
    def shutdown(sig, frame):
        logger.info("Shutdown requested")
        sys.exit(0)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

setup_signal_handlers()

def log_agent_round(round_num: int, tool_calls: List[Dict], response: str, duration_ms: float, request_id: str):
    """Log agent round to JSONL for analysis"""
    try:
        STRUCTURED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STRUCTURED_LOG_FILE, 'a') as f:
            entry = {
                "timestamp": time.time(),
                "request_id": request_id,
                "round": round_num,
                "tool_calls": tool_calls,
                "response_preview": response[:500],
                "duration_ms": round(duration_ms, 2)
            }
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        logger.warning(f"Could not write structured log: {e}")

def extract_native_tool_calls(response: Dict) -> List[ToolInvocation]:
    """Extract tool calls from native OpenAI tool_calls format"""
    invocations = []
    choices = response.get("choices", [])
    if not choices:
        return invocations
    
    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls", [])
    
    for tc in tool_calls:
        function = tc.get("function", {})
        name = function.get("name", "")
        arguments_str = function.get("arguments", "{}")
        
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
            parse_error = None
        except json.JSONDecodeError as e:
            arguments = {}
            parse_error = f"Invalid JSON arguments: {e}"
        
        invocations.append(ToolInvocation(
            name=name,
            arguments=arguments,
            call_id=tc.get("id", generate_call_id()),
            source="native",
            raw_block=arguments_str,
            parse_error=parse_error
        ))
    
    return invocations

def extract_mcp_blocks(text: str) -> List[ToolInvocation]:
    """Extract tool calls from MCP text blocks"""
    invocations = []
    blocks = list(MCPParser.find_blocks(text))
    
    for action, params_str, full_block in blocks:
        parsed_params, parse_error = parse_block(action, params_str)
        if parse_error:
            logger.warning(f"Failed to parse MCP block: {parse_error}")
            invocations.append(ToolInvocation(
                name=action,
                arguments={},
                call_id=generate_call_id(),
                source="mcp",
                raw_block=full_block,
                parse_error=parse_error
            ))
            continue
        
        invocations.append(ToolInvocation(
            name=action,
            arguments=parsed_params or {},
            call_id=generate_call_id(),
            source="mcp",
            raw_block=full_block
        ))
    
    return invocations

def run_agent(original_payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """
    Main agent loop with native tool-call support and MCP block fallback.
    """
    request_id = get_request_id()
    logger.info(f"[{request_id}] Agent request started")
    
    # Handle streaming explicitly
    if original_payload.get("stream", False):
        return {
            "error": {
                "type": "unsupported_feature",
                "message": "Streaming with tool execution is not implemented",
                "param": "stream"
            }
        }, 400
    
    try:
        transcript = copy.deepcopy(original_payload.get("messages", []))
    except Exception as e:
        return {"error": f"Invalid messages structure: {e}"}, 400

    if not transcript:
        return {"error": "No messages provided"}, 400

    # Inject system prompt if not present
    has_system = any(msg.get("role") == "system" for msg in transcript)
    if not has_system:
        transcript.insert(0, {"role": "system", "content": build_system_prompt()})

    # Get OpenAI-compatible tool schemas
    openai_tools = get_openai_tools()
    
    # Track seen tool calls to prevent loops
    seen_calls: Set[str] = set()
    idempotency = get_idempotency_store()
    
    for round_num in range(MAX_TOOL_ROUNDS):
        logger.info(f"[{request_id}] Agent round {round_num + 1}")
        round_start = time.time()

        # Call model with tools
                # ── Deterministic Command Routing ──────────────
        from .router import route_command
        import json
        
        # Get the last user message
        user_content = ""
        for msg in reversed(transcript):
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                break
        
        logger.info(f"[{request_id}] Router input: {repr(user_content)}")
        route = route_command(user_content)
        
        if route:
            tool_name, arguments = route
            logger.info(f"[{request_id}] 🎯 Router matched: {tool_name}")
            
            from .mcp import execute_tool
            success, error, result = execute_tool(tool_name, arguments)
            
            if success:
                logger.info(f"[{request_id}] ✅ Tool executed successfully")
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(result, indent=2)
                        }
                    }]
                }, 200
            else:
                logger.warning(f"[{request_id}] ❌ Tool execution failed: {error}")
                transcript.append({
                    "role": "system",
                    "content": f"Tool {tool_name} failed: {error}"
                })
        
        logger.info(f"[{request_id}] 📡 Calling model...")
        response, status = call_model(
            transcript, 
            original_payload,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto"
        )
        
        logger.info(f"[{request_id}] ✅ Model returned status={status}")
        
        if status != 200:
            error_msg = response.get("error", "Model request failed") if response else "Unknown error"
            return {"error": f"Model error: {error_msg}"}, status

        choices = response.get("choices", [])
        if not choices:
            return {"error": "No choices in response"}, 500

        message = choices[0].get("message", {})
        assistant_content = message.get("content", "")
        tool_calls = []

        # Check for native tool calls first
        logger.info(f"[{request_id}] 🔍 Checking native tool calls...")
        native_calls = extract_native_tool_calls(response)
        logger.info(f"[{request_id}] 📊 native_calls={len(native_calls)}")
        tool_calls.extend(native_calls)
        
        # Also check for MCP blocks in the content (fallback)
        mcp_calls = extract_mcp_blocks(assistant_content)
        tool_calls.extend(mcp_calls)
        
        # FALLBACK: Intent extraction if no MCP blocks found
        logger.info(f"[{request_id}] 📊 final tool_calls count={len(tool_calls)}")
        if not tool_calls:
            from .parser import extract_intent_from_text
            
            # Extract user content from the conversation history
            user_content = ""
            for msg in reversed(transcript):
                if msg.get("role") == "user":
                    user_content = msg.get("content", "")
                    break
            
            logger.info(f"[{request_id}] 🧠 Running intent extraction...")
            intents = extract_intent_from_text(user_content, assistant_content)
            logger.info(f"[{request_id}] 📊 intents={intents}")
            for intent in intents:
                logger.info(f"[{request_id}] 🔧 Intent fallback: detected {intent['name']}")
                tool_calls.append(
                    ToolInvocation(
                        name=intent["name"],
                        arguments=intent["arguments"],
                        call_id=generate_call_id(),
                        source="intent"
                    )
                )
                logger.info(f"[{request_id}] ✅ Added {intent['name']} from intent extraction")

        # Build assistant message for transcript (preserve tool_calls)
        assistant_message = {
            "role": "assistant",
            "content": assistant_content
        }
        if message.get("tool_calls"):
            assistant_message["tool_calls"] = message["tool_calls"]
        
        transcript.append(assistant_message)

        logger.info(f"[{request_id}] 📊 final tool_calls count={len(tool_calls)}")
        if not tool_calls:
            # No tools to execute, return final response
            logger.info(f"[{request_id}] No tool calls, returning final response")
            return response, 200

        # Execute all tools with concurrency limit
        logger.info(f"[{request_id}] Found {len(tool_calls)} tool calls")
        tool_results = []
        tool_call_log = []
        requires_confirmation = False
        pending_tools = []

        for invocation in tool_calls:
            # Check for parse errors
            if invocation.parse_error:
                logger.warning(f"[{request_id}] Tool {invocation.name} parse error: {invocation.parse_error}")
                result_msg = f"Tool {invocation.name} failed to parse: {invocation.parse_error}"
                transcript.append({
                    "role": "tool",
                    "tool_call_id": invocation.call_id,
                    "name": invocation.name,
                    "content": result_msg
                })
                tool_call_log.append({"action": invocation.name, "status": "parse_error", "error": invocation.parse_error})
                continue
            
            # Check for duplicate tool calls within this request (immediate loop protection)
            signature = hashlib.sha256(
                f"{invocation.name}:{json.dumps(invocation.arguments, sort_keys=True)}".encode()
            ).hexdigest()
            
            if signature in seen_calls:
                logger.warning(f"[{request_id}] Duplicate tool call detected: {invocation.name}")
                result_msg = f"Tool {invocation.name} was already called in this conversation. Please try a different action."
                transcript.append({
                    "role": "tool",
                    "tool_call_id": invocation.call_id,
                    "name": invocation.name,
                    "content": result_msg
                })
                tool_call_log.append({"action": invocation.name, "status": "duplicate"})
                continue
            
            # Check idempotency (persistent across requests)
            if idempotency.is_duplicate(invocation.name, invocation.arguments, request_id):
                logger.info(f"[{request_id}] Tool {invocation.name} already executed (idempotent)")
                result_msg = f"Tool {invocation.name} was already executed successfully. Skipping duplicate execution."
                transcript.append({
                    "role": "tool",
                    "tool_call_id": invocation.call_id,
                    "name": invocation.name,
                    "content": result_msg
                })
                tool_call_log.append({"action": invocation.name, "status": "idempotent"})
                continue
            
            seen_calls.add(signature)
            
            # Check policy
            policy = TOOL_POLICY.get(invocation.name, "auto")
            if policy == "confirm":
                # Require confirmation for dangerous tools
                requires_confirmation = True
                pending_tools.append(invocation)
                result_msg = json.dumps({
                    "status": "awaiting_confirmation",
                    "requires_user_confirmation": True,
                    "tool": invocation.name,
                    "arguments": invocation.arguments,
                    "call_id": invocation.call_id,
                    "message": f"User confirmation required for {invocation.name}"
                })
                transcript.append({
                    "role": "tool",
                    "tool_call_id": invocation.call_id,
                    "name": invocation.name,
                    "content": result_msg
                })
                tool_call_log.append({"action": invocation.name, "status": "confirmation_required"})
                continue
            elif policy == "restricted":
                logger.warning(f"[{request_id}] Tool {invocation.name} is restricted")
                result_msg = f"Tool {invocation.name} is restricted and cannot be executed."
                transcript.append({
                    "role": "tool",
                    "tool_call_id": invocation.call_id,
                    "name": invocation.name,
                    "content": result_msg
                })
                tool_call_log.append({"action": invocation.name, "status": "restricted"})
                continue
            
            pending_tools.append(invocation)

        # Execute pending tools with concurrency limit
        logger.info(f"[{request_id}] ⚙️ Executing {len(pending_tools)} tools...")
        if pending_tools and not requires_confirmation:
            # TEMP: Skip tool execution to test
            logger.warning(f"[{request_id}] ⚠️ Tool execution skipped for testing")
            for invocation in pending_tools:
                transcript.append({
                    "role": "tool",
                    "tool_call_id": invocation.call_id,
                    "name": invocation.name,
                    "content": "Tool execution skipped (testing mode)"
                })
            # Skip actual execution
            pass
        elif pending_tools and not requires_confirmation:
            logger.info(f"[{request_id}] Executing {len(pending_tools)} tools (max {MAX_CONCURRENT_TOOLS} concurrent)")
            
            with ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_TOOLS, len(pending_tools))) as executor:
                futures = {}
                for invocation in pending_tools:
                    future = executor.submit(
                        execute_tool_with_context,
                        invocation.name,
                        invocation.arguments,
                        invocation.call_id,
                        request_id
                    )
                    futures[future] = invocation
                
                for future in as_completed(futures):
                    invocation = futures[future]
                    try:
                        success, error, result, duration_ms = future.result()
                        
                        result_msg = f"Tool {invocation.name} {'succeeded' if success else 'failed'}"
                        if success:
                            result_msg += f":\n{json.dumps(result, indent=2)}"
                            idempotency.mark_executed(invocation.name, invocation.arguments, request_id, result)
                        else:
                            result_msg += f": {error}"
                        
                        transcript.append({
                            "role": "tool",
                            "tool_call_id": invocation.call_id,
                            "name": invocation.name,
                            "content": result_msg
                        })
                        
                        tool_call_log.append({
                            "action": invocation.name,
                            "status": "success" if success else "failed",
                            "duration_ms": round(duration_ms, 2)
                        })
                    except Exception as e:
                        logger.error(f"[{request_id}] Tool {invocation.name} execution error: {e}")
                        transcript.append({
                            "role": "tool",
                            "tool_call_id": invocation.call_id,
                            "name": invocation.name,
                            "content": f"Tool {invocation.name} execution error: {str(e)}"
                        })
                        tool_call_log.append({"action": invocation.name, "status": "error", "error": str(e)})

        # Structured logging
        duration_ms = (time.time() - round_start) * 1000
        log_agent_round(round_num + 1, tool_call_log, assistant_content[:500], duration_ms, request_id)
        
        # If confirmation is required, stop the loop and return the state
        if requires_confirmation:
            return {
                "status": "confirmation_required",
                "message": "Tool execution requires user confirmation",
                "pending_tools": [
                    {
                        "name": inv.name,
                        "arguments": inv.arguments,
                        "call_id": inv.call_id
                    }
                    for inv in pending_tools
                ]
            }, 200
        
        # Continue to next round

    logger.warning(f"[{request_id}] Max tool rounds ({MAX_TOOL_ROUNDS}) reached")
    return {"error": f"Maximum tool rounds ({MAX_TOOL_ROUNDS}) exceeded"}, 508

def execute_tool_with_context(name: str, arguments: Dict, call_id: str, request_id: str) -> Tuple[bool, str, Dict, float]:
    """Execute a tool with timing and request context"""
    start_time = time.time()
    try:
        success, error, result = execute_tool(name, arguments)
        duration_ms = (time.time() - start_time) * 1000
        return success, error, result, duration_ms
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return False, str(e), {}, duration_ms
