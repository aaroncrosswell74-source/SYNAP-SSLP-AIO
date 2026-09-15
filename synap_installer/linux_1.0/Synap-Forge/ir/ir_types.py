from enum import Enum
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class IRType(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    PERSONA = "persona"
    BOUNDARY = "boundary"
    DIAGNOSTIC = "diagnostic"
    CONTROL = "control"


class ControlSignal(str, Enum):
    RETRY = "retry"
    HALT = "halt"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    CONTINUE = "continue"


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    HALT = "halt"


@dataclass(frozen=True)
class IRFrame:
    type: IRType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self):
        if not isinstance(self.type, IRType):
            raise ValueError(f"Invalid IRType: {self.type}")
        if not self.content and self.type not in (IRType.BOUNDARY, IRType.CONTROL):
            raise ValueError(f"Empty content for frame type: {self.type}")
        if self.type == IRType.CONTROL:
            signal = self.metadata.get("signal")
            if signal not in [s.value for s in ControlSignal]:
                raise ValueError(f"Invalid control signal: {signal}")

    def to_prompt_string(self) -> str:
        if self.type == IRType.SYSTEM:
            return f"[SYSTEM]: {self.content}"
        elif self.type == IRType.USER:
            return f"{self.metadata.get('user_tag', 'User')}: {self.content}"
        elif self.type == IRType.ASSISTANT:
            return f"{self.metadata.get('assistant_name', 'Assistant')}: {self.content}"
        elif self.type == IRType.PERSONA:
            return f"{self.metadata.get('persona_name', 'Persona')}: {self.content}"
        elif self.type == IRType.BOUNDARY:
            return "---"
        return ""  # DIAGNOSTIC/CONTROL never prompt

    def is_promptable(self) -> bool:
        return self.type in {
            IRType.SYSTEM,
            IRType.USER,
            IRType.ASSISTANT,
            IRType.PERSONA,
            IRType.BOUNDARY,
        }


@dataclass(frozen=True)
class SessionContext:
    frames: Tuple[IRFrame, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def __post_init__(self):
        if not isinstance(self.frames, tuple):
            raise ValueError("frames must be a tuple")

    def get_frame_count(self) -> int:
        return len(self.frames)

    def get_frames_by_type(self, frame_type: IRType) -> List[IRFrame]:
        return [f for f in self.frames if f.type == frame_type]


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    frames: Tuple[IRFrame, ...]
    context: Optional[SessionContext] = None
    prompt: Optional[str] = None
    raw_response: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
