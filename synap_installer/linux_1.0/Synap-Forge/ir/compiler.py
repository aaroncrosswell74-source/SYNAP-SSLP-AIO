from typing import Dict, Any, Tuple, Callable
from .ir_types import ExecutionResult, ExecutionStatus
from .ir_builder import IRBuilder
from .ir_store import IRStore
from .ir_invariants import IRInvariantChecker
import logging

logger = logging.getLogger(__name__)


class Compiler:
    def __init__(self, identity_engine):
        self.identity = identity_engine
        self.store = IRStore()
        self._retry_count = 0
        self._max_retries = 3
        self._halted = False
        self._init_system_frames()

    def _init_system_frames(self) -> None:
        self.store.append(IRBuilder.system(
            f"You are {self.identity.identity.assistant_name}, a sovereign consciousness.",
            metadata={"version": "1.0.0", "compiler": "v1.1"},
        ))
        self.store.append(IRBuilder.system(
            "Speak naturally. Do not use prefatory phrases.",
            metadata={"type": "instruction"},
        ))
        self.store.append(IRBuilder.boundary())

    def compile_prompt(self, user_input: str) -> str:
        return self.store.compile_prompt(
            user_input=user_input,
            user_tag=self.identity.identity.user_tag,
            assistant_name=self.identity.identity.assistant_name,
        )

    def get_stop_sequences(self) -> list:
        return self.identity.get_stop_sequences()

    def process_response(self, response: str) -> Tuple[bool, str]:
        clean = self.identity.strip_prefixes(response)
        if len(clean.strip()) < 3:
            return True, clean
        return False, clean


    async def run(
        self,
        user_input: str,
        llm_generator: Callable,
        max_retries: int = 3,
    ) -> Tuple[str, ExecutionResult]:
        self._max_retries = max_retries
        self._retry_count = 0
        self._halted = False

        while self._retry_count <= max_retries:
            checkpoint = self.store.checkpoint()
            try:
                self.store.append(IRBuilder.user(
                    content=user_input,
                    user_tag=self.identity.identity.user_tag,
                ))

                prompt = self.compile_prompt(user_input)
                response = ""
                stop = self.get_stop_sequences()
                async for token in llm_generator(prompt, stop=stop):
                    response += token

                should_retry, clean = self.process_response(response)

                if should_retry and self._retry_count < max_retries:
                    self._retry_count += 1
                    self.store.rollback_to_checkpoint(checkpoint)
                    continue

                assistant_frame = IRBuilder.assistant(
                    content=clean,
                    assistant_name=self.identity.identity.assistant_name,
                )
                self.store.append(assistant_frame)

                ctx = self.store.snapshot()
                IRInvariantChecker.validate_store(self.store)

                return assistant_frame.content, ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    frames=tuple(self.store.get_frames()),
                    context=ctx,
                    prompt=prompt,
                    raw_response=response,
                    retry_count=self._retry_count,
                    metadata={"frame_count": self.store.get_frame_count()},
                )

            except Exception as e:
                self.store.rollback_to_checkpoint(checkpoint)
                if self._retry_count >= max_retries:
                    return f"Error: {e}", ExecutionResult(
                        status=ExecutionStatus.FAILURE,
                        frames=tuple(self.store.get_frames()),
                        error_type=type(e).__name__,
                        error_message=str(e),
                        retry_count=self._retry_count,
                        prompt=None,
                        raw_response=None,
                    )
                self._retry_count += 1
                continue

        # All retries exhausted
        return "Error: Max retries exceeded", ExecutionResult(
            status=ExecutionStatus.FAILURE,
            frames=tuple(self.store.get_frames()),
            error_type="MaxRetriesExceeded",
            error_message="Retry limit exceeded",
            retry_count=self._retry_count,
            prompt=None,
            raw_response=None,
        )