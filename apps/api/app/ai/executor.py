from collections.abc import Callable
from dataclasses import dataclass
from time import sleep

from app.ai.contracts import AIRequest, AIResponse
from app.ai.errors import (
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderTimeoutExhaustedError,
    AIProviderRetryExhaustedError,
)
from app.ai.execution_policy import ProviderExecutionPolicy
from app.ai.providers.base import AIProvider


@dataclass(frozen=True)
class ProviderExecutionResult:
    response: AIResponse
    attempt_count: int
    final_attempt_number: int
    retry_performed: bool


class ProviderRetryExecutor:
    def __init__(self, *, sleep_func: Callable[[float], None] | None = None) -> None:
        self._sleep = sleep_func or sleep

    def execute(
        self,
        *,
        provider: AIProvider,
        request: AIRequest,
        policy: ProviderExecutionPolicy,
    ) -> ProviderExecutionResult:
        last_error: AIProviderError | None = None
        retry_performed = False
        for attempt_number in range(1, policy.max_attempts + 1):
            attempt_request = request.model_copy(
                update={
                    "timeout_seconds": policy.timeout_seconds,
                    "metadata": {
                        **request.metadata,
                        "attempt_number": attempt_number,
                        "max_attempts": policy.max_attempts,
                    },
                }
            )
            try:
                response = provider.generate(attempt_request, timeout_seconds=policy.timeout_seconds)
                return ProviderExecutionResult(
                    response=response,
                    attempt_count=attempt_number,
                    final_attempt_number=attempt_number,
                    retry_performed=retry_performed,
                )
            except AIProviderError as exc:
                last_error = exc
                if exc.code not in policy.retryable_error_types:
                    _annotate_error(
                        exc,
                        attempt_count=attempt_number,
                        final_attempt_number=attempt_number,
                        retry_performed=retry_performed,
                    )
                    raise
                if attempt_number >= policy.max_attempts:
                    break
                retry_performed = True
                self._sleep(self._backoff_seconds(attempt_number, policy))

        assert last_error is not None
        if isinstance(last_error, AIProviderTimeoutError):
            error = AIProviderTimeoutExhaustedError(
                "Provider timeout retry attempts exhausted.",
                last_error_code=last_error.code,
            )
        else:
            error = AIProviderRetryExhaustedError(
                "Provider retry attempts exhausted.",
                last_error_code=last_error.code,
            )
        _annotate_error(
            error,
            attempt_count=policy.max_attempts,
            final_attempt_number=policy.max_attempts,
            retry_performed=retry_performed,
        )
        raise error

    @staticmethod
    def _backoff_seconds(attempt_number: int, policy: ProviderExecutionPolicy) -> float:
        return min(policy.retry_backoff_seconds * attempt_number, 5.0)


def _annotate_error(
    error: AIProviderError,
    *,
    attempt_count: int,
    final_attempt_number: int,
    retry_performed: bool,
) -> None:
    error.attempt_count = attempt_count
    error.final_attempt_number = final_attempt_number
    error.retry_performed = retry_performed
