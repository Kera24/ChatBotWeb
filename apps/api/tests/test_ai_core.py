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

from decimal import Decimal

from app.ai.accounting import AIExecutionOutcome, AIUsageAccountingRepository, AIUsageAccountingService
from app.ai.errors import AIProviderError, AIProviderTimeoutError


def test_ai_usage_accounting_records_successful_execution() -> None:
    container = create_ai_core()

    response = container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
            execution_id="success-record",
        )
    )
    records = container.accounting_service.list_recent()

    assert len(records) == 1
    record = records[0]
    assert record.execution_id == "success-record"
    assert record.outcome == AIExecutionOutcome.SUCCESS
    assert record.prompt_tokens == response.token_usage.input_tokens
    assert record.completion_tokens == response.token_usage.output_tokens
    assert record.total_tokens == response.token_usage.total_tokens
    assert record.finish_reason == FinishReason.STOP


def test_ai_usage_accounting_zero_cost_mock_model() -> None:
    container = create_ai_core()

    container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
            execution_id="zero-cost",
        )
    )
    record = container.accounting_service.list_recent()[0]

    assert record.estimated_input_cost == Decimal("0")
    assert record.estimated_output_cost == Decimal("0")
    assert record.total_estimated_cost == Decimal("0")


def test_ai_usage_accounting_deterministic_cost_calculation() -> None:
    container = create_ai_core()
    model = container.model_registry.get("mock-grounded-answer")
    priced_model = model.model_copy(
        update={
            "model_key": "priced-mock",
            "input_cost_per_million_tokens": Decimal("2.50"),
            "output_cost_per_million_tokens": Decimal("10.00"),
        }
    )
    container.model_registry.register(priced_model)

    response = container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="priced-mock",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
            execution_id="priced-cost",
        )
    )
    record = container.accounting_service.list_recent()[0]

    expected_input = (Decimal(response.token_usage.input_tokens) / Decimal(1_000_000)) * Decimal("2.50")
    expected_output = (Decimal(response.token_usage.output_tokens) / Decimal(1_000_000)) * Decimal("10.00")
    assert record.estimated_input_cost == expected_input
    assert record.estimated_output_cost == expected_output
    assert record.total_estimated_cost == expected_input + expected_output


def test_ai_usage_accounting_records_failed_execution() -> None:
    container = create_ai_core()

    with pytest.raises(AIProviderError):
        container.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer",
                model_key="mock-grounded-answer",
                variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
                execution_id="failed-record",
                simulate_failure=True,
            )
        )
    record = container.accounting_service.list_recent()[0]

    assert record.execution_id == "failed-record"
    assert record.outcome == AIExecutionOutcome.FAILED
    assert record.finish_reason == FinishReason.ERROR
    assert record.error_code == "AI_PROVIDER_ERROR"
    assert record.total_tokens == record.prompt_tokens
    assert record.completion_tokens == 0


def test_ai_usage_accounting_records_timeout_execution() -> None:
    container = create_ai_core()

    with pytest.raises(AIProviderTimeoutError):
        container.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer",
                model_key="mock-grounded-answer",
                variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
                execution_id="timeout-record",
                simulate_timeout=True,
            )
        )
    record = container.accounting_service.list_recent()[0]

    assert record.execution_id == "timeout-record"
    assert record.outcome == AIExecutionOutcome.TIMEOUT
    assert record.finish_reason == FinishReason.TIMEOUT
    assert record.error_code == "AI_PROVIDER_TIMEOUT_EXHAUSTED"


def test_ai_usage_accounting_preserves_provider_model_prompt_metadata() -> None:
    container = create_ai_core()

    response = container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
            execution_id="metadata-record",
            organisation_id="org-1",
            workspace_id="workspace-1",
        )
    )
    record = container.accounting_service.list_recent()[0]

    assert record.organisation_id == "org-1"
    assert record.workspace_id == "workspace-1"
    assert record.provider_key == response.provider_key
    assert record.model_key == response.model_key
    assert record.provider_model_name == response.provider_model_name
    assert record.prompt_key == response.prompt_key
    assert record.prompt_version == response.prompt_version
    assert record.prompt_hash == response.prompt_hash


def test_ai_usage_accounting_duplicate_execution_ids_rejected() -> None:
    repository = AIUsageAccountingRepository()
    service = AIUsageAccountingService(repository)
    container = create_ai_core()
    response = container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
        )
    )
    request = make_request()
    model = container.model_registry.get("mock-grounded-answer")

    service.record_success(execution_id="duplicate", request=request, response=response, model=model)
    with pytest.raises(ValueError):
        service.record_success(execution_id="duplicate", request=request, response=response, model=model)

from app.ai.errors import (
    AIProviderRetryExhaustedError,
    AIProviderTimeoutExhaustedError,
    ProviderNotFoundError,
)
from app.ai.execution_policy import ProviderExecutionPolicy
from app.ai.executor import ProviderRetryExecutor
from app.ai.health import ProviderHealthService, ProviderHealthStatus
from app.ai.providers.mock import MockAIProvider


def test_provider_execution_successful_first_attempt_records_attempt_metadata() -> None:
    container = create_ai_core()

    container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
            execution_id="first-attempt",
        )
    )
    record = container.accounting_service.list_recent()[0]

    assert record.attempt_count == 1
    assert record.final_attempt_number == 1
    assert record.retry_performed is False
    assert record.timeout_seconds == container.execution_policy.timeout_seconds
    assert record.provider_health_at_start == "unknown"
    assert record.provider_health_at_end == "healthy"


def test_provider_execution_transient_failure_then_success_retries_deterministically() -> None:
    container = create_ai_core()

    response = container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
            execution_id="retry-success",
            simulate_transient_failures=1,
        )
    )
    record = container.accounting_service.list_recent()[0]

    assert response.metadata["attempt_number"] == 2
    assert record.attempt_count == 2
    assert record.final_attempt_number == 2
    assert record.retry_performed is True
    assert record.outcome == AIExecutionOutcome.SUCCESS


def test_provider_execution_retry_exhaustion_records_failure() -> None:
    container = create_ai_core()

    with pytest.raises(AIProviderRetryExhaustedError):
        container.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer",
                model_key="mock-grounded-answer",
                variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
                execution_id="retry-exhausted",
                simulate_transient_failures=5,
            )
        )
    record = container.accounting_service.list_recent()[0]

    assert record.error_code == "AI_PROVIDER_RETRY_EXHAUSTED"
    assert record.attempt_count == container.execution_policy.max_attempts
    assert record.retry_performed is True
    assert record.provider_health_at_end == "unavailable"


def test_provider_execution_non_retryable_failure_performs_no_retry() -> None:
    container = create_ai_core()

    with pytest.raises(AIProviderError):
        container.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer",
                model_key="mock-grounded-answer",
                variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
                execution_id="no-retry-failure",
                simulate_failure=True,
            )
        )
    record = container.accounting_service.list_recent()[0]

    assert record.error_code == "AI_PROVIDER_ERROR"
    assert record.attempt_count == 1
    assert record.retry_performed is False


def test_provider_execution_timeout_retry_exhaustion_records_timeout() -> None:
    container = create_ai_core()

    with pytest.raises(AIProviderTimeoutExhaustedError):
        container.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer",
                model_key="mock-grounded-answer",
                variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
                execution_id="timeout-exhausted",
                simulate_timeout=True,
            )
        )
    record = container.accounting_service.list_recent()[0]

    assert record.outcome == AIExecutionOutcome.TIMEOUT
    assert record.error_code == "AI_PROVIDER_TIMEOUT_EXHAUSTED"
    assert record.attempt_count == container.execution_policy.max_attempts
    assert record.retry_performed is True


def test_provider_retry_executor_respects_max_attempts_and_backoff_sequence() -> None:
    sleeps: list[float] = []
    executor = ProviderRetryExecutor(sleep_func=sleeps.append)
    policy = ProviderExecutionPolicy(max_attempts=3, retry_backoff_seconds=0.25, timeout_seconds=3)
    provider = MockAIProvider()
    request = make_request(simulate_transient_failures=2)

    result = executor.execute(provider=provider, request=request, policy=policy)

    assert result.attempt_count == 3
    assert result.retry_performed is True
    assert sleeps == [0.25, 0.5]


def test_provider_health_checks_and_states_are_deterministic() -> None:
    provider = MockAIProvider()
    health = provider.health()
    assert health.status == ProviderHealthStatus.HEALTHY
    assert health.metadata["network"] is False

    provider.set_health_status(ProviderHealthStatus.DEGRADED)
    assert provider.health().status == ProviderHealthStatus.DEGRADED

    provider.set_health_status(ProviderHealthStatus.UNAVAILABLE)
    assert provider.health().status == ProviderHealthStatus.UNAVAILABLE


def test_provider_health_service_unknown_provider_rejected() -> None:
    registry = ProviderRegistry()
    health_service = ProviderHealthService(registry)

    with pytest.raises(ProviderNotFoundError):
        health_service.get("missing")


def test_provider_execution_updates_health_state() -> None:
    container = create_ai_core()

    container.service.generate(
        AICoreGenerateInput(
            prompt_key="grounded_rag_answer",
            model_key="mock-grounded-answer",
            variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
        )
    )
    assert container.health_service.get("mock").status == ProviderHealthStatus.HEALTHY

    with pytest.raises(AIProviderError):
        container.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer",
                model_key="mock-grounded-answer",
                variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
                simulate_failure=True,
            )
        )
    assert container.health_service.get("mock").status == ProviderHealthStatus.UNAVAILABLE


def test_provider_health_fail_fast_records_accounting_when_required() -> None:
    container = create_ai_core()
    provider = container.provider_registry.get("mock")
    provider.set_health_status(ProviderHealthStatus.DEGRADED)
    container.service.execution_policy = container.execution_policy.model_copy(update={"health_check_required": True})

    with pytest.raises(AIProviderError):
        container.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer",
                model_key="mock-grounded-answer",
                variables={"question": "What is Yoranix?", "context": "[1] Yoranix is an AI platform."},
                execution_id="fail-fast-degraded",
            )
        )
    record = container.accounting_service.list_recent()[0]

    assert record.error_code == "AI_PROVIDER_DEGRADED"
    assert record.attempt_count == 0
    assert record.provider_health_at_start == "degraded"
    assert record.provider_health_at_end == "degraded"
