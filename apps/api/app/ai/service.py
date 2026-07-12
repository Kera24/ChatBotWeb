from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.ai.accounting import AIExecutionOutcome, AIUsageAccountingService
from app.ai.contracts import AIMessage, AIRequest, AIResponse, FinishReason, MessageRole
from app.ai.errors import (
    AIProviderDegradedError,
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderTimeoutExhaustedError,
    AIProviderUnavailableError,
)
from app.ai.execution_policy import ProviderExecutionPolicy
from app.ai.executor import ProviderRetryExecutor
from app.ai.health import ProviderHealthService, ProviderHealthStatus
from app.ai.model_registry import ModelRegistry
from app.ai.prompt_registry import PromptRegistry
from app.ai.provider_registry import ProviderRegistry


@dataclass(frozen=True)
class AICoreGenerateInput:
    prompt_key: str
    model_key: str
    variables: dict[str, Any]
    execution_id: str | None = None
    simulate_failure: bool = False
    simulate_timeout: bool = False
    simulate_transient_failures: int = 0
    timeout_seconds: float | None = None
    organisation_id: str | None = None
    workspace_id: str | None = None


class AICoreService:
    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        model_registry: ModelRegistry,
        prompt_registry: PromptRegistry,
        accounting_service: AIUsageAccountingService,
        health_service: ProviderHealthService,
        retry_executor: ProviderRetryExecutor,
        execution_policy: ProviderExecutionPolicy,
    ) -> None:
        self.provider_registry = provider_registry
        self.model_registry = model_registry
        self.prompt_registry = prompt_registry
        self.accounting_service = accounting_service
        self.health_service = health_service
        self.retry_executor = retry_executor
        self.execution_policy = execution_policy

    def generate(self, request_input: AICoreGenerateInput) -> AIResponse:
        model = self.model_registry.get(request_input.model_key, require_enabled=True)
        provider = self.provider_registry.get(model.provider_key)
        rendered_prompt = self.prompt_registry.render(
            request_input.prompt_key,
            request_input.variables,
        )
        execution_id = request_input.execution_id or self.accounting_service.create_execution_id()
        policy = self.execution_policy.model_copy(
            update={"timeout_seconds": request_input.timeout_seconds or self.execution_policy.timeout_seconds}
        )
        ai_request = AIRequest(
            organisation_id=request_input.organisation_id,
            workspace_id=request_input.workspace_id,
            provider_key=provider.provider_key,
            model_key=model.model_key,
            provider_model_name=model.provider_model_name,
            prompt_key=rendered_prompt.prompt_key,
            prompt_version=rendered_prompt.version,
            prompt_hash=rendered_prompt.prompt_hash,
            messages=[
                AIMessage(role=MessageRole.SYSTEM, content=rendered_prompt.system_prompt),
                AIMessage(role=MessageRole.USER, content=rendered_prompt.user_prompt),
            ],
            timeout_seconds=policy.timeout_seconds,
            metadata={
                "execution_id": execution_id,
                "simulate_failure": request_input.simulate_failure,
                "simulate_timeout": request_input.simulate_timeout,
                "simulate_transient_failures": request_input.simulate_transient_failures,
            },
        )
        health_at_start = self.health_service.get(provider.provider_key)
        if policy.health_check_required:
            health_at_start = self.health_service.check_provider(provider)
            try:
                self._fail_fast_if_unhealthy(policy, health_at_start.status)
            except AIProviderError as exc:
                self.accounting_service.record_failure(
                    execution_id=execution_id,
                    request=ai_request,
                    model=model,
                    latency_ms=0,
                    outcome=AIExecutionOutcome.FAILED,
                    finish_reason=FinishReason.ERROR,
                    error_code=exc.code,
                    error_message=exc.message,
                    attempt_count=0,
                    final_attempt_number=0,
                    retry_performed=False,
                    timeout_seconds=policy.timeout_seconds,
                    provider_health_at_start=health_at_start.status,
                    provider_health_at_end=health_at_start.status,
                )
                raise

        started_at = perf_counter()
        try:
            execution = self.retry_executor.execute(provider=provider, request=ai_request, policy=policy)
        except AIProviderError as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            health_at_end = self.health_service.update_after_failure(provider.provider_key, message=exc.message)
            outcome = AIExecutionOutcome.TIMEOUT if isinstance(exc, (AIProviderTimeoutError, AIProviderTimeoutExhaustedError)) else AIExecutionOutcome.FAILED
            finish_reason = FinishReason.TIMEOUT if outcome == AIExecutionOutcome.TIMEOUT else FinishReason.ERROR
            self.accounting_service.record_failure(
                execution_id=execution_id,
                request=ai_request,
                model=model,
                latency_ms=latency_ms,
                outcome=outcome,
                finish_reason=finish_reason,
                error_code=exc.code,
                error_message=exc.message,
                attempt_count=int(getattr(exc, "attempt_count", 1)),
                final_attempt_number=int(getattr(exc, "final_attempt_number", 1)),
                retry_performed=bool(getattr(exc, "retry_performed", False)),
                timeout_seconds=policy.timeout_seconds,
                provider_health_at_start=health_at_start.status,
                provider_health_at_end=health_at_end.status,
            )
            raise

        latency_ms = int((perf_counter() - started_at) * 1000)
        response = execution.response.model_copy(update={"latency_ms": latency_ms})
        health_at_end = self.health_service.update_after_success(provider.provider_key)
        self.accounting_service.record_success(
            execution_id=execution_id,
            request=ai_request,
            response=response,
            model=model,
            attempt_count=execution.attempt_count,
            final_attempt_number=execution.final_attempt_number,
            retry_performed=execution.retry_performed,
            timeout_seconds=policy.timeout_seconds,
            provider_health_at_start=health_at_start.status,
            provider_health_at_end=health_at_end.status,
        )
        return response

    @staticmethod
    def _fail_fast_if_unhealthy(policy: ProviderExecutionPolicy, status: ProviderHealthStatus) -> None:
        if not policy.fail_fast_when_unhealthy:
            return
        if status == ProviderHealthStatus.UNAVAILABLE:
            raise AIProviderUnavailableError("Provider is unavailable and fail-fast policy is enabled.")
        if status == ProviderHealthStatus.DEGRADED:
            raise AIProviderDegradedError("Provider is degraded and fail-fast policy is enabled.")
