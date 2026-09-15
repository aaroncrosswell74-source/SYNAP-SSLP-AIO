"""Deterministic command router for obvious tool commands"""

import re
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("Router")

# Precise patterns to avoid false positives
COMMANDS = [
  COMMANDS = [
    # ──────────────────────────────────────────────────────────────
    # ADB DEVICES - More flexible matching
    # ──────────────────────────────────────────────────────────────
    (r"\b(list|show|get)\s+(my\s+)?devices?\b", "adb_devices", {}),
    (r"\b(list|show|get)\b.*\bandroid\b.*\bdevices?\b", "adb_devices", {}),
    (r"^adb devices$", "adb_devices", {}),
    (r"\bconnected\s+devices?\b", "adb_devices", {}),
    (r"\bdevices?\b.*\b(connected|available)\b", "adb_devices", {}),
    (r"\b(what|which)\s+devices?\b", "adb_devices", {}),  # "What devices are connected?"
    
    # ──────────────────────────────────────────────────────────────
    # ADB SHELL
    # ──────────────────────────────────────────────────────────────
    (r"\b(run|execute)\s+(a\s+)?shell\s+command\b", "adb_shell", {}),
    (r"\badb\s+shell\b", "adb_shell", {}),
    (r"^shell$", "adb_shell", {}),
    (r"\bshell\s+ls\b", "adb_shell", {}),
    (r"\b(execute|run)\s+command\s+on\s+device\b", "adb_shell", {}),
    
    # ──────────────────────────────────────────────────────────────
    # ADB INSTALL
    # ──────────────────────────────────────────────────────────────
    (r"\binstall\s+(the\s+)?apk\b", "adb_install", {}),
    (r"\binstall\s+(the\s+)?app\b", "adb_install", {}),
    (r"\binstall\s+(the\s+)?application\b", "adb_install", {}),
    (r"\badb\s+install\b", "adb_install", {}),
    (r"\b(put|get)\s+app\s+on\s+device\b", "adb_install", {}),
    
    # ──────────────────────────────────────────────────────────────
    # BATTERY (NEW!)
    # ──────────────────────────────────────────────────────────────
    (r"\b(battery|power)\s+(level|status|check)\b", "adb_shell", {"command": "dumpsys battery | grep level"}),
    (r"\b(check|show|get)\s+battery\b", "adb_shell", {"command": "dumpsys battery | grep level"}),
    (r"\bhow\s+(is|much)\s+battery\b", "adb_shell", {"command": "dumpsys battery | grep level"}),
    
    # ──────────────────────────────────────────────────────────────
    # GRADLE BUILD
    # ──────────────────────────────────────────────────────────────
    (r"\b(build|compile)\s+(the\s+)?apk\b", "gradle_build", {}),
    (r"\b(build|compile)\s+(the\s+)?android\s+app\b", "gradle_build", {}),
    (r"\bgradle\s+build\b", "gradle_build", {}),
    (r"^build$", "gradle_build", {}),
    (r"\b(make|create)\s+apk\b", "gradle_build", {}),
    
    # ──────────────────────────────────────────────────────────────
    # GIT COMMIT
    # ──────────────────────────────────────────────────────────────
    (r"\b(git\s+)?commit\b", "git_commit", {}),
    (r"\bcommit\s+(my\s+)?changes\b", "git_commit", {}),
    (r"\b(save|store)\s+changes\b", "git_commit", {}),
    
    # ──────────────────────────────────────────────────────────────
    # GIT PUSH
    # ──────────────────────────────────────────────────────────────
    (r"\b(git\s+)?push\b", "git_push", {}),
    (r"\bpush\s+(to\s+)?remote\b", "git_push", {}),
    (r"\b(upload|send)\s+to\s+github\b", "git_push", {}),
    
    # ──────────────────────────────────────────────────────────────
    # SEARCH MEMORY
    # ──────────────────────────────────────────────────────────────
    (r"\b(search|find|lookup)\s+(in\s+)?memory\b", "search_memory", {}),
    (r"\b(remember|recall)\s+(.+)\b", "search_memory", {}),
    (r"\bwhat\s+do\s+you\s+know\s+about\b", "search_memory", {}),
    
    # ──────────────────────────────────────────────────────────────
    # INGEST MEMORY
    # ──────────────────────────────────────────────────────────────
    (r"\b(store|save|remember)\s+(this|that)\b", "ingest_memory", {}),
    (r"\bremember\s+this\b", "ingest_memory", {}),
    (r"\bsave\s+to\s+memory\b", "ingest_memory", {}),
    (r"\b(memorize|learn)\s+this\b", "ingest_memory", {}),
    
    # ──────────────────────────────────────────────────────────────
    # READ FILE
    # ──────────────────────────────────────────────────────────────
    (r"\b(read|cat|display|show)\s+(file|code|source)\b", "read_file", {}),
    (r"\b(open|view)\s+file\b", "read_file", {}),
    
    # ──────────────────────────────────────────────────────────────
    # LIST DIRECTORY
    # ──────────────────────────────────────────────────────────────
    (r"\b(list|show)\s+(directory|folder|contents)\b", "list_directory", {}),
    (r"\b(ls|dir)\b", "list_directory", {}),
    (r"\bwhat('s| is) in (this|the) folder\b", "list_directory", {}),
]

def route_command(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Route a user command to a tool if it matches known patterns.
    Returns (tool_name, params) or None if no match.
    """
    if not text or not isinstance(text, str):
        return None

    text_lower = text.lower().strip()

    for pattern, tool_name, params in COMMANDS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.info(f"Router matched '{text}' → {tool_name}")
            return (tool_name, params.copy())

    logger.debug(f"Router: no match for '{text}'")
    return None