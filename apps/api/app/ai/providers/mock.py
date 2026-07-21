from datetime import UTC, datetime
from hashlib import sha256

from app.ai.contracts import (
    AIRequest,
    AIResponse,
    FinishReason,
    ProviderMetadata,
    TokenUsage,
)
from app.ai.errors import AIProviderError, AIProviderTimeoutError, AIProviderUnavailableError
from app.ai.health import ProviderHealth, ProviderHealthStatus
from app.ai.providers.base import AIProvider, ProviderCapabilities


class MockAIProvider(AIProvider):
    provider_key = "mock"
    display_name = "Deterministic Mock AI Provider"
    capabilities = ProviderCapabilities(streaming=False, json_mode=False, tools=False, vision=False)

    def __init__(self, *, health_status: ProviderHealthStatus = ProviderHealthStatus.HEALTHY) -> None:
        self.health_status = health_status

    def set_health_status(self, status: ProviderHealthStatus) -> None:
        self.health_status = status

    def generate(self, request: AIRequest, *, timeout_seconds: float | None = None) -> AIResponse:
        attempt_number = int(request.metadata.get("attempt_number", 1))
        transient_failures = int(request.metadata.get("simulate_transient_failures", 0) or 0)
        if request.metadata.get("simulate_timeout"):
            raise AIProviderTimeoutError("Mock provider timeout simulation requested.")
        if transient_failures and attempt_number <= transient_failures:
            raise AIProviderUnavailableError("Mock provider transient unavailable simulation requested.")
        if request.metadata.get("simulate_failure"):
            raise AIProviderError("Mock provider failure simulation requested.")

        prompt_text = "\n".join(message.content for message in request.messages)
        digest = sha256(prompt_text.encode("utf-8")).hexdigest()[:16]
        generated = f"[mock:{digest}] Deterministic mock response for prompt {request.prompt_key}@{request.prompt_version}."
        usage = TokenUsage(
            input_tokens=self._estimate_tokens(prompt_text),
            output_tokens=self._estimate_tokens(generated),
            total_tokens=self._estimate_tokens(prompt_text) + self._estimate_tokens(generated),
            estimated=True,
        )
        return AIResponse(
            text=generated,
            provider_key=self.provider_key,
            model_key=request.model_key,
            provider_model_name=request.provider_model_name,
            prompt_key=request.prompt_key,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            token_usage=usage,
            latency_ms=0,
            finish_reason=FinishReason.STOP,
            provider_metadata=ProviderMetadata(
                provider_key=self.provider_key,
                provider_model_name=request.provider_model_name,
                response_id=f"mock-{digest}",
                raw_finish_reason="stop",
                metadata={"digest": digest, "network": False, "deterministic": True, "attempt_number": attempt_number},
            ),
            metadata={"mock": True, "digest": digest, "attempt_number": attempt_number},
        )

    def health(self) -> ProviderHealth:
        messages = {
            ProviderHealthStatus.HEALTHY: "Mock provider is healthy.",
            ProviderHealthStatus.DEGRADED: "Mock provider degraded simulation active.",
            ProviderHealthStatus.UNAVAILABLE: "Mock provider unavailable simulation active.",
            ProviderHealthStatus.UNKNOWN: "Mock provider health is unknown.",
        }
        return ProviderHealth(
            provider_key=self.provider_key,
            status=self.health_status,
            checked_at=datetime.now(UTC),
            message=messages[self.health_status],
            metadata={"network": False, "deterministic": True},
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text.split())) if text else 0
