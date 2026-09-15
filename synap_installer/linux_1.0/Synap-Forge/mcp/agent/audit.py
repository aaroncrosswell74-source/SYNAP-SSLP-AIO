"""Audit logging for compliance and security"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from .config import LOG_DIR
from .context import get_request_id

AUDIT_LOG_FILE = LOG_DIR / "audit.jsonl"

def log_audit_event(
    event_type: str,
    tool_name: Optional[str] = None,
    arguments_hash: Optional[str] = None,
    user_id: Optional[str] = None,
    status: str = "success",
    duration_ms: float = 0,
    error: Optional[str] = None
):
    """Log an audit event for compliance"""
    try:
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "request_id": get_request_id(),
            "user_id": user_id or "unknown",
            "status": status,
            "duration_ms": round(duration_ms, 2)
        }
        
        if tool_name:
            event["tool"] = tool_name
        if arguments_hash:
            event["arguments_hash"] = arguments_hash
        if error:
            event["error"] = error[:200]  # Truncate for safety
        
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(json.dumps(event) + '\n')
    except Exception as e:
        print(f"Failed to write audit log: {e}")

def hash_arguments(arguments: Dict) -> str:
    """Hash arguments for audit logging (avoid logging sensitive data)"""
    # Sort keys for consistent hashing
    sorted_args = json.dumps(arguments, sort_keys=True)
    return hashlib.sha256(sorted_args.encode()).hexdigest()[:16]
