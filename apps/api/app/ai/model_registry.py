from decimal import Decimal

from pydantic import BaseModel

from app.ai.errors import ModelDisabledError, ModelNotFoundError
from app.ai.provider_registry import ProviderRegistry


class ModelCapabilities(BaseModel):
    streaming: bool = False
    json_mode: bool = False
    tools: bool = False
    vision: bool = False


class ModelConfig(BaseModel):
    model_key: str
    provider_key: str
    provider_model_name: str
    display_name: str
    enabled: bool = True
    context_window: int
    input_cost_per_million_tokens: Decimal | None = None
    output_cost_per_million_tokens: Decimal | None = None
    # Bumped manually whenever this model's configured pricing changes, so
    # historical AI trace/cost rows can be told apart from rows priced under
    # a different rate - the "versioned price snapshot" requirement without a
    # separate pricing-config subsystem.
    cost_calc_version: str = "v1"
    capabilities: ModelCapabilities = ModelCapabilities()


class ModelRegistry:
    def __init__(self, provider_registry: ProviderRegistry) -> None:
        self._provider_registry = provider_registry
        self._models: dict[str, ModelConfig] = {}

    def register(self, model: ModelConfig) -> None:
        if model.model_key in self._models:
            raise ValueError(f"Model already registered: {model.model_key}")
        self._provider_registry.get(model.provider_key)
        self._models[model.model_key] = model

    def get(self, model_key: str, *, require_enabled: bool = True) -> ModelConfig:
        model = self._models.get(model_key)
        if model is None:
            raise ModelNotFoundError(f"Model not found: {model_key}")
        if require_enabled and not model.enabled:
            raise ModelDisabledError(f"Model is disabled: {model_key}")
        self._provider_registry.get(model.provider_key)
        return model

    def list(self) -> list[ModelConfig]:
        return list(self._models.values())


def register_default_mock_model(registry: ModelRegistry) -> None:
    registry.register(
        ModelConfig(
            model_key="mock-grounded-answer",
            provider_key="mock",
            provider_model_name="mock-local-v1",
            display_name="Mock Grounded Answer Model",
            enabled=True,
            context_window=16000,
            input_cost_per_million_tokens=Decimal("0"),
            output_cost_per_million_tokens=Decimal("0"),
            capabilities=ModelCapabilities(streaming=False, json_mode=False, tools=False, vision=False),
        )
    )


def register_openrouter_model(
    registry: ModelRegistry,
    *,
    provider_model_name: str,
    model_key: str = "openrouter-default",
    context_window: int = 128_000,
) -> None:
    # Per-model pricing on OpenRouter varies by the underlying model chosen
    # via OPENROUTER_MODEL and isn't known statically here, so cost fields are
    # left unset rather than guessed. app.ai.accounting._rate_to_decimal
    # treats an unset rate as $0/token (same as the mock model), so estimated
    # cost will read as zero until real per-model pricing is configured here -
    # tracked as a known follow-up, not a launch blocker for provider wiring.
    registry.register(
        ModelConfig(
            model_key=model_key,
            provider_key="openrouter",
            provider_model_name=provider_model_name,
            display_name=f"OpenRouter: {provider_model_name}",
            enabled=True,
            context_window=context_window,
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            capabilities=ModelCapabilities(streaming=False, json_mode=False, tools=False, vision=False),
        )
    )
