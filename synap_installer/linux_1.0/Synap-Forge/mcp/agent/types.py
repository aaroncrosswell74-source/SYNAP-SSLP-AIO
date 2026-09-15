"""Core types for the agent runtime"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import uuid

@dataclass
class ToolInvocation:
    """Normalized tool invocation from any source"""
    name: str
    arguments: Dict[str, Any]
    call_id: str
    source: str  # "native" or "mcp"
    raw_block: Optional[str] = None
    parse_error: Optional[str] = None

def generate_call_id() -> str:
    """Generate a unique tool call ID"""
    return f"call_{uuid.uuid4().hex[:12]}"

@dataclass
class ToolResult:
    """Result of a tool execution"""
    invocation: ToolInvocation
    success: bool
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    requires_confirmation: bool = False

@dataclass
class AgentRound:
    """One iteration of the agent loop"""
    round_num: int
    assistant_content: str
    tool_invocations: List[ToolInvocation]
    tool_results: List[ToolResult]
    duration_ms: float
    has_tool_calls: bool = False
    requires_confirmation: bool = False
