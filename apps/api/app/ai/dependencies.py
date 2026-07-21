from dataclasses import dataclass

from fastapi import Request

from app.ai.accounting import AIUsageAccountingRepository, AIUsageAccountingService
from app.ai.execution_policy import ProviderExecutionPolicy
from app.ai.executor import ProviderRetryExecutor
from app.ai.health import ProviderHealthService
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
    accounting_repository: AIUsageAccountingRepository
    accounting_service: AIUsageAccountingService
    health_service: ProviderHealthService
    retry_executor: ProviderRetryExecutor
    execution_policy: ProviderExecutionPolicy
    service: AICoreService


def create_ai_core() -> AICoreContainer:
    provider_registry = ProviderRegistry()
    provider_registry.register(MockAIProvider())

    model_registry = ModelRegistry(provider_registry)
    register_default_mock_model(model_registry)

    prompt_registry = PromptRegistry()
    register_default_grounded_rag_prompt(prompt_registry)

    accounting_repository = AIUsageAccountingRepository()
    accounting_service = AIUsageAccountingService(accounting_repository)
    health_service = ProviderHealthService(provider_registry)
    retry_executor = ProviderRetryExecutor()
    execution_policy = ProviderExecutionPolicy(timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS)

    service = AICoreService(
        provider_registry=provider_registry,
        model_registry=model_registry,
        prompt_registry=prompt_registry,
        accounting_service=accounting_service,
        health_service=health_service,
        retry_executor=retry_executor,
        execution_policy=execution_policy,
    )
    return AICoreContainer(
        provider_registry=provider_registry,
        model_registry=model_registry,
        prompt_registry=prompt_registry,
        accounting_repository=accounting_repository,
        accounting_service=accounting_service,
        health_service=health_service,
        retry_executor=retry_executor,
        execution_policy=execution_policy,
        service=service,
    )


def get_ai_core(request: Request) -> AICoreContainer:
    return request.app.state.ai_core


def get_default_ai_timeout() -> float:
    return settings.AI_REQUEST_TIMEOUT_SECONDS
