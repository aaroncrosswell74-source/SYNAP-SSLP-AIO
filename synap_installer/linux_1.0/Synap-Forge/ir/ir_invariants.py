from .ir_types import IRFrame, IRType, SessionContext
from .ir_store import IRStore


class IRInvariantError(Exception):
    pass


class IRInvariantChecker:
    @staticmethod
    def validate_store(store: IRStore) -> None:
        IRInvariantChecker._validate_frames(store.get_frames())

    @staticmethod
    def validate_context(ctx: SessionContext) -> None:
        IRInvariantChecker._validate_frames(list(ctx.frames))

    @staticmethod
    def _validate_frames(frames):
        IRInvariantChecker._check_append_only(frames)
        IRInvariantChecker._check_system_order(frames)
        IRInvariantChecker._check_control_internal(frames)

    @staticmethod
    def _check_append_only(frames):
        seen_ids = set()
        last_ts = 0.0
        for f in frames:
            if f.id in seen_ids:
                raise IRInvariantError(f"Duplicate frame id: {f.id}")
            seen_ids.add(f.id)
            if f.timestamp < last_ts:
                raise IRInvariantError("Non-monotonic timestamps in IR")
            last_ts = f.timestamp

    @staticmethod
    def _check_system_order(frames):
        seen_non_system = False
        for f in frames:
            if f.type != IRType.SYSTEM:
                seen_non_system = True
            elif seen_non_system:
                raise IRInvariantError("SYSTEM frame appears after non-system frame")

    @staticmethod
    def _check_control_internal(frames):
        for f in frames:
            if f.type == IRType.CONTROL and f.content.strip():
                raise IRInvariantError("Control frame has non-empty content")
