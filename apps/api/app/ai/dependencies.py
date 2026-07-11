from dataclasses import dataclass

from fastapi import Request

from app.ai.model_registry import ModelRegistry, register_default_mock_model
from app.ai.prompt_registry import PromptRegistry, register_default_grounded_rag_prompt
from app.ai.provider_registry import ProviderRegistry
from app.ai.providers.mock import MockAIProvider
from app.ai.service import AICoreService
from app.core.config import settings


@dataclass
class AICoreContainer:
    provider_registry: ProviderRegistry
    model_registry: ModelRegistry
    prompt_registry: PromptRegistry
    service: AICoreService


def create_ai_core() -> AICoreContainer:
    provider_registry = ProviderRegistry()
    provider_registry.register(MockAIProvider())

    model_registry = ModelRegistry(provider_registry)
    register_default_mock_model(model_registry)

    prompt_registry = PromptRegistry()
    register_default_grounded_rag_prompt(prompt_registry)

    service = AICoreService(
        provider_registry=provider_registry,
        model_registry=model_registry,
        prompt_registry=prompt_registry,
    )
    return AICoreContainer(
        provider_registry=provider_registry,
        model_registry=model_registry,
        prompt_registry=prompt_registry,
        service=service,
    )


def get_ai_core(request: Request) -> AICoreContainer:
    return request.app.state.ai_core


def get_default_ai_timeout() -> float:
    return settings.AI_REQUEST_TIMEOUT_SECONDS
