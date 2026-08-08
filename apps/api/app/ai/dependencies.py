from dataclasses import dataclass

from fastapi import Request

from app.ai.accounting import AIUsageAccountingRepository, AIUsageAccountingService
from app.ai.errors import AIProviderConfigurationError
from app.ai.execution_policy import ProviderExecutionPolicy
from app.ai.executor import ProviderRetryExecutor
from app.ai.health import ProviderHealthService
from app.ai.model_registry import ModelRegistry, register_default_mock_model, register_openrouter_model
from app.ai.prompt_registry import PromptRegistry, register_default_grounded_rag_prompt
from app.ai.provider_registry import ProviderRegistry
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.openrouter import OpenRouterAIProvider
from app.ai.service import AICoreService
from app.core.config import settings

# development/test: AI_PROVIDER left at its "mock" default is allowed - see
# _assert_mock_provider_allowed. Any other APP_ENV must configure a real
# provider; this is the "no silent mock fallback in production" guarantee
# from the launch-readiness review (P0-1).
_NON_PRODUCTION_APP_ENVS = {"development", "test", "testing"}


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
    # MockAIProvider is always registered - kept available for tests/dev
    # regardless of AI_PROVIDER, per the provider-selection policy below.
    provider_registry.register(MockAIProvider())

    model_registry = ModelRegistry(provider_registry)
    register_default_mock_model(model_registry)

    _configure_selected_provider(provider_registry, model_registry)

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


def _configure_selected_provider(provider_registry: ProviderRegistry, model_registry: ModelRegistry) -> None:
    """Registers whichever real provider AI_PROVIDER selects, and enforces
    the provider-selection policy from the launch-readiness review (P0-1):
    development/test may run on the mock provider, but any other APP_ENV must
    have a real provider configured - create_ai_core() (called once at
    app startup, see app.main.create_app) raises immediately rather than
    silently serving mock responses."""
    provider_key = settings.AI_PROVIDER.strip().lower()
    if provider_key == "mock":
        _assert_mock_provider_allowed()
        return
    if provider_key == "openrouter":
        provider_registry.register(_build_openrouter_provider())
        register_openrouter_model(model_registry, provider_model_name=settings.OPENROUTER_MODEL)
        return
    raise AIProviderConfigurationError(
        f"Unsupported AI_PROVIDER {settings.AI_PROVIDER!r}. Supported values: 'mock', 'openrouter'."
    )


def _assert_mock_provider_allowed() -> None:
    if settings.APP_ENV.strip().lower() in _NON_PRODUCTION_APP_ENVS:
        return
    raise AIProviderConfigurationError(
        f"AI_PROVIDER is 'mock' (the default) but APP_ENV={settings.APP_ENV!r} is not a development/test "
        "environment. Refusing to silently serve deterministic mock AI responses outside development/test - "
        "set AI_PROVIDER=openrouter and the required OPENROUTER_API_KEY/OPENROUTER_MODEL settings to configure "
        "a real generation provider."
    )


def _build_openrouter_provider() -> OpenRouterAIProvider:
    if not settings.OPENROUTER_API_KEY:
        raise AIProviderConfigurationError("AI_PROVIDER=openrouter requires OPENROUTER_API_KEY to be set.")
    if not settings.OPENROUTER_MODEL:
        raise AIProviderConfigurationError(
            "AI_PROVIDER=openrouter requires OPENROUTER_MODEL to be set (e.g. 'openai/gpt-4o-mini')."
        )
    return OpenRouterAIProvider(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_output_tokens=settings.LLM_MAX_TOKENS,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )
