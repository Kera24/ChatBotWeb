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
    input_cost_per_million_tokens: float | None = None
    output_cost_per_million_tokens: float | None = None
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
            capabilities=ModelCapabilities(streaming=False, json_mode=False, tools=False, vision=False),
        )
    )
