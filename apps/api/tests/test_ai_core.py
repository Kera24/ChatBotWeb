import pytest
from pydantic import ValidationError

from app.ai.contracts import (
    AIMessage,
    AIRequest,
    AIResponse,
    FinishReason,
    MessageRole,
    ProviderMetadata,
    TokenUsage,
)
from app.ai.errors import AIProviderError, AIProviderTimeoutError, ProviderNotFoundError
from app.ai.model_registry import ModelCapabilities, ModelConfig, ModelRegistry, register_default_mock_model
from app.ai.prompt_registry import (
    PromptDefinition,
    PromptRegistry,
    PromptVersion,
    register_default_grounded_rag_prompt,
    stable_prompt_hash,
)
from app.ai.provider_registry import ProviderRegistry
from app.ai.providers.mock import MockAIProvider
from app.ai.service import AICoreGenerateInput
from app.ai.dependencies import create_ai_core
from app.ai.errors import ModelDisabledError, PromptValidationError


def make_request(**metadata: object) -> AIRequest:
    return AIRequest(
        provider_key="mock",
        model_key="mock-grounded-answer",
        provider_model_name="mock-local-v1",
        prompt_key="grounded_rag_answer",
        prompt_version="v1",
        prompt_hash="hash",
        messages=[
            AIMessage(role=MessageRole.SYSTEM, content="Answer from context only."),
            AIMessage(role=MessageRole.USER, content="Question: What is Yoranix?"),
        ],
        metadata=dict(metadata),
    )


def test_provider_neutral_contracts_serialise_correctly() -> None:
    response = AIResponse(
        text="hello",
        provider_key="mock",
        model_key="mock-grounded-answer",
        provider_model_name="mock-local-v1",
        prompt_key="grounded_rag_answer",
        prompt_version="v1",
        prompt_hash="abc123",
        token_usage=TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5),
        latency_ms=7,
        finish_reason=FinishReason.STOP,
        provider_metadata=ProviderMetadata(provider_key="mock", provider_model_name="mock-local-v1"),
    )

    payload = response.model_dump(mode="json")

    assert payload["text"] == "hello"
    assert payload["finish_reason"] == "stop"
    assert payload["token_usage"]["total_tokens"] == 5


def test_ai_request_contract_is_immutable() -> None:
    request = make_request()

    with pytest.raises(ValidationError):
        request.model_key = "changed"  # type: ignore[misc]


def test_mock_provider_output_is_deterministic_and_identifiable() -> None:
    provider = MockAIProvider()
    request = make_request()

    first = provider.generate(request)
    second = provider.generate(request)

    assert first.text == second.text
    assert first.text.startswith("[mock:")
    assert first.provider_metadata.metadata["deterministic"] is True
    assert first.provider_metadata.metadata["network"] is False


def test_mock_provider_token_estimates_are_stable() -> None:
    provider = MockAIProvider()
    request = make_request()

    first = provider.generate(request).token_usage
    second = provider.generate(request).token_usage

    assert first == second
    assert first.total_tokens == first.input_tokens + first.output_tokens
    assert first.estimated is True


def test_mock_provider_failure_and_timeout_simulation() -> None:
    provider = MockAIProvider()

    with pytest.raises(AIProviderError):
        provider.generate(make_request(simulate_failure=True))

    with pytest.raises(AIProviderTimeoutError):
        provider.generate(make_request(simulate_timeout=True))


def test_provider_registry_registers_lists_and_rejects_duplicates() -> None:
    registry = ProviderRegistry()
    provider = MockAIProvider()

    registry.register(provider)

    assert registry.get("mock") is provider
    assert registry.list() == [provider]
    assert registry.health()[0].provider_key == "mock"
    with pytest.raises(ValueError):
        registry.register(MockAIProvider())


def test_provider_registry_missing_provider_error() -> None:
    registry = ProviderRegistry()

    with pytest.raises(ProviderNotFoundError):
        registry.get("missing")


def test_model_registry_registration_resolution_and_default() -> None:
    providers = ProviderRegistry()
    providers.register(MockAIProvider())
    models = ModelRegistry(providers)
    register_default_mock_model(models)

    model = models.get("mock-grounded-answer")

    assert model.provider_key == "mock"
    assert model.provider_model_name == "mock-local-v1"


def test_model_registry_rejects_duplicates_and_disabled_execution() -> None:
    providers = ProviderRegistry()
    providers.register(MockAIProvider())
    models = ModelRegistry(providers)
    model = ModelConfig(
        model_key="local",
        provider_key="mock",
        provider_model_name="mock-local-v1",
        display_name="Local Mock",
        enabled=True,
        context_window=1000,
        capabilities=ModelCapabilities(),
    )
    models.register(model)

    with pytest.raises(ValueError):
        models.register(model)

    models.register(model.model_copy(update={"model_key": "disabled", "enabled": False}))
    with pytest.raises(ModelDisabledError):
        models.get("disabled")


def test_model_registry_requires_existing_provider() -> None:
    models = ModelRegistry(ProviderRegistry())

    with pytest.raises(ProviderNotFoundError):
        models.register(
            ModelConfig(
                model_key="orphan",
                provider_key="missing",
                provider_model_name="missing-model",
                display_name="Missing",
                context_window=1000,
            )
        )


def test_prompt_registry_definition_versions_and_active_resolution() -> None:
    registry = PromptRegistry()
    definition = PromptDefinition(
        prompt_key="answer",
        display_name="Answer",
        description="Answer prompt",
        category="rag",
    )
    registry.register_definition(definition)
    prompt_hash = stable_prompt_hash(
        prompt_key="answer",
        version="v1",
        system_template="Use {context}",
        user_template="Question {question}",
        required_variables=("context", "question"),
    )
    version = PromptVersion(
        prompt_key="answer",
        version="v1",
        system_template="Use {context}",
        user_template="Question {question}",
        required_variables=("context", "question"),
        status="active",
        prompt_hash=prompt_hash,
    )

    registry.register_version(version)

    assert registry.get_definition("answer") == definition
    assert registry.resolve_active("answer") == version
    assert registry.render("answer", {"context": "sources", "question": "Why?"}).user_prompt == "Question Why?"
    with pytest.raises(ValueError):
        registry.register_version(version)


def test_prompt_registry_required_variables_hash_and_immutability() -> None:
    registry = PromptRegistry()
    register_default_grounded_rag_prompt(registry)
    active = registry.resolve_active("grounded_rag_answer")

    assert active.prompt_hash == stable_prompt_hash(
        prompt_key=active.prompt_key,
        version=active.version,
        system_template=active.system_template,
        user_template=active.user_template,
        required_variables=active.required_variables,
        optional_variables=active.optional_variables,
    )
    with pytest.raises(PromptValidationError):
        registry.render("grounded_rag_answer", {"question": "What?"})
    with pytest.raises(ValidationError):
        active.system_template = "changed"  # type: ignore[misc]


def test_prompt_registry_rendered_default_prompt_correctness() -> None:
    registry = PromptRegistry()
    register_default_grounded_rag_prompt(registry)

    rendered = registry.render("grounded_rag_answer", {"question": "What is X?", "context": "[1] X is safe."})

    assert "Do not guess" in rendered.system_prompt
    assert "What is X?" in rendered.user_prompt
    assert "[1] X is safe." in rendered.user_prompt


def test_ai_core_successful_execution_includes_metadata() -> None:
    container = create_ai_core()

    response = container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
        )
    )

    assert response.provider_key == "mock"
    assert response.model_key == "mock-grounded-answer"
    assert response.provider_model_name == "mock-local-v1"
    assert response.prompt_key == "grounded_rag_answer"
    assert response.prompt_version == "v1"
    assert response.prompt_hash
    assert response.token_usage.total_tokens > 0
    assert response.finish_reason == FinishReason.STOP
