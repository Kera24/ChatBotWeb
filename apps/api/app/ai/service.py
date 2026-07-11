from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.ai.contracts import AIMessage, AIRequest, AIResponse, MessageRole
from app.ai.model_registry import ModelRegistry
from app.ai.prompt_registry import PromptRegistry
from app.ai.provider_registry import ProviderRegistry


@dataclass(frozen=True)
class AICoreGenerateInput:
    prompt_key: str
    model_key: str
    variables: dict[str, Any]
    simulate_failure: bool = False
    simulate_timeout: bool = False
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
    ) -> None:
        self.provider_registry = provider_registry
        self.model_registry = model_registry
        self.prompt_registry = prompt_registry

    def generate(self, request_input: AICoreGenerateInput) -> AIResponse:
        model = self.model_registry.get(request_input.model_key, require_enabled=True)
        provider = self.provider_registry.get(model.provider_key)
        rendered_prompt = self.prompt_registry.render(
            request_input.prompt_key,
            request_input.variables,
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
            timeout_seconds=request_input.timeout_seconds,
            metadata={
                "simulate_failure": request_input.simulate_failure,
                "simulate_timeout": request_input.simulate_timeout,
            },
        )
        started_at = perf_counter()
        response = provider.generate(ai_request, timeout_seconds=request_input.timeout_seconds)
        latency_ms = int((perf_counter() - started_at) * 1000)
        return response.model_copy(update={"latency_ms": latency_ms})
