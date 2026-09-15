from typing import List, Optional
from .ir_types import IRFrame, SessionContext
import logging

logger = logging.getLogger(__name__)


class IRStore:
    def __init__(self):
        self._frames: List[IRFrame] = []
        self._checkpoints: List[int] = []

    def append(self, frame: IRFrame) -> None:
        if not isinstance(frame, IRFrame):
            raise ValueError(f"Invalid frame type: {type(frame)}")
        self._frames.append(frame)

    def pop(self) -> Optional[IRFrame]:
        if not self._frames:
            return None
        return self._frames.pop()

    def get_frames(self) -> List[IRFrame]:
        return self._frames.copy()

    def get_frame_count(self) -> int:
        return len(self._frames)

    def checkpoint(self) -> int:
        cp = len(self._frames)
        self._checkpoints.append(cp)
        return cp

    def rollback_to_checkpoint(self, checkpoint: int) -> int:
        if checkpoint not in self._checkpoints:
            raise ValueError(f"Checkpoint {checkpoint} not found")
        if checkpoint > len(self._frames):
            raise ValueError(f"Checkpoint {checkpoint} > frame count {len(self._frames)}")
        removed = len(self._frames) - checkpoint
        self._frames = self._frames[:checkpoint]
        self._checkpoints = [c for c in self._checkpoints if c <= checkpoint]
        return removed

    def rollback_to_last_checkpoint(self) -> int:
        if not self._checkpoints:
            return 0
        return self.rollback_to_checkpoint(self._checkpoints[-1])

    def snapshot(self, metadata: dict = None) -> SessionContext:
        return SessionContext(
            frames=tuple(self._frames),
            metadata=metadata or {
                "frame_count": len(self._frames),
                "checkpoint_count": len(self._checkpoints),
            },
        )

    def clear(self) -> None:
        self._frames = []
        self._checkpoints = []

    def compile_prompt(self, user_input: str, user_tag: str, assistant_name: str) -> str:
        parts = []
        for frame in self._frames:
            if frame.is_promptable():
                s = frame.to_prompt_string()
                if s:
                    parts.append(s)
        parts.append(f"{assistant_name}:")
        return "\n".join(parts)
