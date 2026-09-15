# FIXED: ir/compiler.py run() method - Iterative retry loop
# Replaces the recursive call at line 77 with a while loop
# Confirmed: This removes the stack overflow risk

async def run(
    self,
    user_input: str,
    llm_generator: Callable,
    max_retries: int = 3,
) -> Tuple[str, ExecutionResult]:
    self._max_retries = max_retries
    self._retry_count = 0
    self._halted = False

    # Iterative retry loop - stack safe
    while self._retry_count <= self._max_retries:
        checkpoint = self.store.checkpoint()
        
        try:
            # Store user input
            self.store.append(IRBuilder.user(
                content=user_input,
                user_tag=self.identity.identity.user_tag,
            ))

            # Build prompt and get response
            prompt = self.compile_prompt(user_input)
            response = ""
            stop = self.get_stop_sequences()
            async for token in llm_generator(prompt, stop=stop):
                response += token

            # Process response
            should_retry, clean = self.process_response(response)

            if should_retry:
                self._retry_count += 1
                self.store.rollback_to_checkpoint(checkpoint)
                continue  # Retry with clean state

            # Success path
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
            self._retry_count += 1
            
            if self._retry_count > self._max_retries:
                return f"Error: {e}", ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    frames=tuple(self.store.get_frames()),
                    error_type=type(e).__name__,
                    error_message=str(e),
                    retry_count=self._retry_count,
                )
            continue  # Retry on exception

    # All retries exhausted
    return "Error: Max retries exceeded", ExecutionResult(
        status=ExecutionStatus.FAILURE,
        frames=tuple(self.store.get_frames()),
        error_type="MaxRetriesExceeded",
        error_message=f"Failed after {self._max_retries} retries",
        retry_count=self._retry_count,
    )
