from typing import Dict, Any
from .ir_types import IRFrame, IRType, ControlSignal


class IRBuilder:
    @staticmethod
    def system(content: str, metadata: Dict[str, Any] = None) -> IRFrame:
        return IRFrame(IRType.SYSTEM, content, metadata or {})

    @staticmethod
    def user(content: str, user_tag: str = "User", metadata: Dict[str, Any] = None) -> IRFrame:
        meta = metadata or {}
        meta["user_tag"] = user_tag
        return IRFrame(IRType.USER, content, meta)

    @staticmethod
    def assistant(content: str, assistant_name: str = "Assistant", metadata: Dict[str, Any] = None) -> IRFrame:
        meta = metadata or {}
        meta["assistant_name"] = assistant_name
        return IRFrame(IRType.ASSISTANT, content, meta)

    @staticmethod
    def persona(content: str, persona_name: str = "Persona", metadata: Dict[str, Any] = None) -> IRFrame:
        meta = metadata or {}
        meta["persona_name"] = persona_name
        return IRFrame(IRType.PERSONA, content, meta)

    @staticmethod
    def boundary(metadata: Dict[str, Any] = None) -> IRFrame:
        return IRFrame(IRType.BOUNDARY, "---", metadata or {})

    @staticmethod
    def diagnostic(content: str, metadata: Dict[str, Any] = None) -> IRFrame:
        return IRFrame(IRType.DIAGNOSTIC, content, metadata or {})

    @staticmethod
    def control(signal: ControlSignal, payload: Dict[str, Any] = None) -> IRFrame:
        return IRFrame(
            IRType.CONTROL,
            "",
            {"signal": signal.value, "payload": payload or {}},
        )
