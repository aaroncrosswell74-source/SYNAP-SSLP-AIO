"""MCP block parser - state machine, not regex"""

import json
from typing import Tuple, Optional, Iterator

class MCPParser:
    """Simple state machine for parsing [MCP: ...] blocks"""
    
    @staticmethod
    def find_blocks(text: str) -> Iterator[Tuple[str, str, str]]:
        """
        Yield (action, params_json, full_block) for each MCP block found.
        Handles nested JSON correctly.
        """
        i = 0
        while i < len(text):
            # Find "[MCP:"
            start = text.find("[MCP:", i)
            if start == -1:
                break
            
            # Find the action name (word after [MCP:)
            j = start + 5  # after "[MCP:"
            while j < len(text) and text[j].isspace():
                j += 1
            
            action_start = j
            while j < len(text) and (text[j].isalnum() or text[j] == '_'):
                j += 1
            
            action = text[action_start:j]
            
            # Now parse the JSON object
            json_start = j
            while j < len(text) and text[j].isspace():
                j += 1
            
            if j >= len(text) or text[j] != '{':
                # No JSON object found, skip this block
                i = j + 1
                continue
            
            # Parse balanced JSON
            brace_count = 0
            in_string = False
            escape = False
            
            while j < len(text):
                char = text[j]
                
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            j += 1
                            break
                
                j += 1
            
            if j >= len(text) or brace_count != 0:
                # Unbalanced JSON, skip
                i = j + 1
                continue
            
            params_str = text[json_start:j].strip()
            
            # Expect ']' after the JSON
            k = j
            while k < len(text) and text[k].isspace():
                k += 1
            
            if k < len(text) and text[k] == ']':
                j = k + 1  # Include the ']'
            else:
                # No closing bracket, but still use the block
                pass
            
            full_block = text[start:j]
            yield action, params_str, full_block
            i = j

def parse_block(action: str, params_str: str) -> Tuple[Optional[dict], Optional[str]]:
    """Parse params JSON. Returns (params, error_message)"""
    try:
        params = json.loads(params_str) if params_str else {}
        return params, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in params: {e}"

def extract_intent_from_text(text: str, user_text: str = "") -> list:
    """
    Best-effort intent extraction with question filtering.
    """
    source = (user_text or text).lower()

    # Guard: Do not execute tools for informational questions
    question_markers = [
        "what is", "what are", "how does", "how do i", 
        "why", "explain", "tell me about", "what devices", "which devices", "can you list", "can you show"
    ]
    if any(q in source for q in question_markers):
        return []

    intents = [
        (
            "adb_devices", 
            [
                "list devices", "connected devices", "android devices", "adb devices", 
                "show my phone", "list android", "connected android",
                "show connected devices", "what devices are connected", "list my devices", "show my devices"
            ], 
            {}
        ),
        (
            "adb_install", 
            [
                "install apk", "install app", "install application", "install my apk", "install the apk"
            ], 
            {}
        ),
        (
            "adb_shell", 
            [
                "run shell", "execute shell", "adb shell", "shell command", "run command"
            ], 
            {}
        ),
        (
            "gradle_build", 
            [
                "gradle build", "build project", "build my android project", "build android project", "android build", "assemble debug", "build gradle", "assemble"
            ], 
            {"task": "assembleDebug"}
        ),
        (
            "git_commit", 
            [
                "git commit", "commit changes", "commit files", "save changes"
            ], 
            {"message": "Auto-commit from Synap"}
        ),
    ]
    
    results = []
    for name, patterns, args in intents:
        if any(pattern in source for pattern in patterns):
            results.append({"name": name, "arguments": args})
            break
    return results
