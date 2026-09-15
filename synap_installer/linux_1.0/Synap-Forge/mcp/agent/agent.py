
import logging
import time
import copy
import hashlib
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path

from .tools import get_tool
from .mcp import execute_tool
from .model import call_model
from .parser import MCPParser, parse_block
from .prompt import build_system_prompt

logger = logging.getLogger("Agent")
STRUCTURED_LOG_FILE = Path("agent_rounds.jsonl")
MAX_TOOL_ROUNDS = 5

def log_agent_round(round_num: int, tool_calls: List[Dict], response: str, duration_ms: float):
    """Log agent round to JSONL for analysis"""
    try:
        with open(STRUCTURED_LOG_FILE, 'a') as f:
            entry = {
                "timestamp": time.time(),
                "round": round_num,
                "tool_calls": tool_calls,
                "response_preview": response[:500],
                "duration_ms": round(duration_ms, 2)
            }
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        logger.warning(f"Could not write structured log: {e}")

def run_agent(original_payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """
    Main agent loop with:
    - Deep copy to avoid mutation
    - Immediate duplicate detection
    - Bounded iterations
    - Structured logging
    - Clean transcript management
    """
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

    # Track the last tool called to detect immediate repeats
    last_tool_signature = None
    
    for round_num in range(MAX_TOOL_ROUNDS):
        logger.info(f"🔄 Agent round {round_num + 1}")
        round_start = time.time()

        # ── Deterministic Command Routing ──────────────
        from .router import route_command
        import json

        user_content = ""
        for msg in reversed(transcript):
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                break

        logger.info(f"Router input: {repr(user_content)}")
        route = route_command(user_content)

        if route:
            tool_name, arguments = route
            logger.info(f"🎯 Router matched: {tool_name}")
            logger.info(f"Arguments: {arguments}")

            success, error, result = execute_tool(
                tool_name,
                arguments
            )

            if success:
                logger.info("✅ Tool executed successfully")
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                result,
                                indent=2
                            )
                        }
                    }]
                }, 200

            logger.warning(
                f"❌ Tool execution failed: {error}"
            )

        # Call model
        response, status = call_model(transcript, original_payload)
        if status != 200:
            error_msg = response.get("error", "Model request failed") if response else "Unknown error"
            return {"error": f"Model error: {error_msg}"}, status

        choices = response.get("choices", [])
        if not choices:
            return {"error": "No choices in response"}, 500

        assistant_msg = choices[0].get("message", {})
        assistant_content = assistant_msg.get("content", "")

        # Append assistant response to transcript
        transcript.append({"role": "assistant", "content": assistant_content})

        # Check for MCP blocks using the state machine parser
        blocks = list(MCPParser.find_blocks(assistant_content))
        if not blocks:
            # No tools to execute, return final response
            return response, 200

        # Execute all tools found
        logger.info(f"🔧 Found {len(blocks)} MCP blocks")
        tool_calls = []

        for action, params_str, full_block in blocks:
            # Parse params
            parsed_params, parse_error = parse_block(action, params_str)
            if parse_error:
                tool_result = f"Tool {action} failed to parse: {parse_error}"
                transcript.append({"role": "tool", "content": tool_result, "tool_name": action})
                tool_calls.append({"action": action, "status": "parse_error", "error": parse_error})
                continue

            # Check for immediate duplicate tool call
            sig = hashlib.md5(f"{action}:{json.dumps(parsed_params, sort_keys=True)}".encode()).hexdigest()
            if sig == last_tool_signature:
                logger.warning(f"⚠️ Immediate duplicate tool call detected: {action}")
                tool_result = f"Tool {action} was just called. Please try a different action or ask for clarification."
                transcript.append({"role": "tool", "content": tool_result, "tool_name": action})
                tool_calls.append({"action": action, "status": "duplicate"})
                continue

            last_tool_signature = sig

            # Execute tool
            success, error, result = execute_tool(action, parsed_params)
            if success:
                tool_result = f"Tool {action} succeeded:\n{json.dumps(result, indent=2)}"
            else:
                tool_result = f"Tool {action} failed: {error}"
            
            transcript.append({"role": "tool", "content": tool_result, "tool_name": action})
            tool_calls.append({"action": action, "status": "success" if success else "failed"})

            # Replace the block in the assistant's message with a marker
            # But preserve the original message by appending a new one
            # Actually, don't modify history - just append tool results
            pass

        # Structured logging
        duration_ms = (time.time() - round_start) * 1000
        log_agent_round(round_num + 1, tool_calls, assistant_content[:500], duration_ms)

        # Continue to next round

    # Max rounds reached
    logger.warning(f"⚠️ Max tool rounds ({MAX_TOOL_ROUNDS}) reached")
    return {"error": f"Maximum tool rounds ({MAX_TOOL_ROUNDS}) exceeded"}, 508