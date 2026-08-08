"""Tests for AI_PROVIDER-driven provider selection (P0-1 of the launch
readiness review). Covers create_ai_core()'s wiring/validation policy
directly, and the end-to-end RAGOrchestrator path with a real
OpenRouterAIProvider (network intercepted via httpx.MockTransport) to prove
observability records the real provider/model, not the mock ones."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.dependencies import create_ai_core
from app.ai.errors import AIProviderConfigurationError
from app.ai.rag_orchestrator import RAGOrchestrationRequest, RAGOrchestrator, RAGOrchestratorDependencies
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.embeddings import LocalMockEmbeddingProvider

_FAKE_API_KEY = "".join(("sk-or-v1-", "abcdefghijklmnopqrstuvwx0123456789"))


@contextmanager
def _settings_override(**overrides: Any) -> Iterator[None]:
    originals = {name: getattr(settings, name) for name in overrides}
    for name, value in overrides.items():
        object.__setattr__(settings, name, value)
    try:
        yield
    finally:
        for name, value in originals.items():
            object.__setattr__(settings, name, value)


# --- create_ai_core() provider-selection policy ------------------------------


def test_create_ai_core_defaults_to_mock_in_development() -> None:
    with _settings_override(APP_ENV="development", AI_PROVIDER="mock"):
        container = create_ai_core()
    assert container.provider_registry.get("mock") is not None
    assert container.model_registry.get("mock-grounded-answer").provider_key == "mock"


def test_create_ai_core_refuses_silent_mock_fallback_in_production() -> None:
    with _settings_override(APP_ENV="production", AI_PROVIDER="mock"):
        with pytest.raises(AIProviderConfigurationError, match="Refusing to silently serve"):
            create_ai_core()


@pytest.mark.parametrize("app_env", ["staging", "pilot", ""])
def test_create_ai_core_refuses_silent_mock_fallback_outside_dev_test(app_env: str) -> None:
    with _settings_override(APP_ENV=app_env, AI_PROVIDER="mock"):
        with pytest.raises(AIProviderConfigurationError):
            create_ai_core()


def test_create_ai_core_openrouter_missing_api_key_fails_clearly() -> None:
    with _settings_override(APP_ENV="production", AI_PROVIDER="openrouter", OPENROUTER_API_KEY="", OPENROUTER_MODEL="openai/gpt-4o-mini"):
        with pytest.raises(AIProviderConfigurationError, match="OPENROUTER_API_KEY"):
            create_ai_core()


def test_create_ai_core_openrouter_missing_model_fails_clearly() -> None:
    with _settings_override(APP_ENV="production", AI_PROVIDER="openrouter", OPENROUTER_API_KEY=_FAKE_API_KEY, OPENROUTER_MODEL=""):
        with pytest.raises(AIProviderConfigurationError, match="OPENROUTER_MODEL"):
            create_ai_core()


def test_create_ai_core_unsupported_provider_fails_clearly() -> None:
    with _settings_override(APP_ENV="development", AI_PROVIDER="anthropic-direct"):
        with pytest.raises(AIProviderConfigurationError, match="Unsupported AI_PROVIDER"):
            create_ai_core()


def test_create_ai_core_openrouter_registers_provider_and_model_and_keeps_mock_for_tests() -> None:
    with _settings_override(
        APP_ENV="production",
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=_FAKE_API_KEY,
        OPENROUTER_MODEL="openai/gpt-4o-mini",
        DEFAULT_AI_MODEL_KEY="openrouter-default",
    ):
        container = create_ai_core()

    # Real provider is registered and selected as the default...
    provider = container.provider_registry.get("openrouter")
    assert provider.provider_key == "openrouter"
    model = container.model_registry.get("openrouter-default")
    assert model.provider_key == "openrouter"
    assert model.provider_model_name == "openai/gpt-4o-mini"
    # ...but MockAIProvider is still available for tests/development, per
    # requirement 3 ("Keep MockAIProvider for tests/development").
    assert container.provider_registry.get("mock") is not None
    assert container.model_registry.get("mock-grounded-answer").provider_key == "mock"


# --- end-to-end: RAGOrchestrator + observability with a real OpenRouter call (network mocked) ---


class _CapturingTraceRecorder:
    def __init__(self) -> None:
        self.finish_trace_calls: list[dict[str, Any]] = []
        self.model_calls: list[dict[str, Any]] = []

    def start_trace(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_stage(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_retrieval(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_guardrail(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_model_call(self, ctx: Any, **kwargs: Any) -> None:
        self.model_calls.append(kwargs)

    def finish_trace(self, ctx: Any, **kwargs: Any) -> None:
        self.finish_trace_calls.append(kwargs)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    with TestingSession() as session:
        yield session
    Base.metadata.drop_all(engine)


def _seed_tenant_with_chunk(db: Session) -> tuple[str, str]:
    unique = uuid4().hex[:8]
    organisation = Organisation(name="OpenRouter Test Org", slug=f"openrouter-test-{unique}")
    user = User(email=f"owner-{unique}@example.test")
    workspace = Workspace(organisation=organisation, name="Knowledge Base", slug=f"openrouter-test-{unique}-kb")
    membership = Membership(organisation=organisation, user=user, role="org_owner")
    db.add_all([organisation, user, workspace, membership])
    db.commit()

    document = Document(
        organisation_id=organisation.id, workspace_id=workspace.id, title="Refund Policy",
        source_type="txt", source_key="refund-policy.txt", status="ready",
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        organisation_id=organisation.id, workspace_id=workspace.id, document_id=document.id,
        version_number=1, checksum="checksum-refund", processing_status="ready",
    )
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    chunk = Chunk(
        organisation_id=organisation.id, workspace_id=workspace.id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content="Refunds are available within 30 days of purchase.", content_hash="hash-refund",
        token_count=8, source_type="txt", source_title="Refund Policy", status="ready",
        embedding_provider="local-mock", embedding_model="rag-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    )
    db.add(chunk)
    db.commit()
    return organisation.id, workspace.id


def test_rag_orchestrator_answers_via_openrouter_and_records_real_provider_in_observability(db_session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "gen-xyz",
                "model": "openai/gpt-4o-mini",
                "choices": [{"message": {"role": "assistant", "content": "Refunds are available within 30 days."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 8, "total_tokens": 38},
            },
        )

    with _settings_override(
        APP_ENV="production",
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=_FAKE_API_KEY,
        OPENROUTER_MODEL="openai/gpt-4o-mini",
        DEFAULT_AI_MODEL_KEY="openrouter-default",
        EMBEDDING_PROVIDER="local-mock",
        EMBEDDING_MODEL="rag-test",
        EMBEDDING_DIMENSION=8,
        RETRIEVAL_MAX_CONTEXT_CHUNKS=5,
        RETRIEVAL_MAX_CONTEXT_CHARS=1000,
        RETRIEVAL_MIN_SIMILARITY_SCORE=0.0,
    ):
        ai_core = create_ai_core()
        openrouter_provider = ai_core.provider_registry.get("openrouter")
        # Swap in a mock-transport client so this test makes zero real network
        # calls, while exercising the exact same create_ai_core() wiring and
        # OpenRouterAIProvider.generate() code path production uses.
        openrouter_provider._client = httpx.Client(transport=httpx.MockTransport(handler))

        organisation_id, workspace_id = _seed_tenant_with_chunk(db_session)
        embedding_provider = LocalMockEmbeddingProvider(dimension=8, model_name="rag-test")
        trace_recorder = _CapturingTraceRecorder()

        orchestrator = RAGOrchestrator(
            RAGOrchestratorDependencies(db=db_session, ai_core=ai_core, embedding_provider=embedding_provider, trace_recorder=trace_recorder)
        )
        result = orchestrator.answer(
            RAGOrchestrationRequest(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                query="Refunds are available within 30 days of purchase.",
                channel="dashboard_test",
            )
        )

    # The answer came from the real OpenRouterAIProvider path, not the mock.
    assert result.answer == "Refunds are available within 30 days."
    assert result.provider_key == "openrouter"
    assert result.model_key == "openrouter-default"
    assert result.provider_model_name == "openai/gpt-4o-mini"
    assert result.token_usage.total_tokens == 38

    # Observability (app.observability.ai_trace_recorder) recorded the real
    # provider/model, not "mock"/"mock-grounded-answer".
    assert trace_recorder.model_calls, "record_model_call was never invoked"
    model_call = trace_recorder.model_calls[-1]
    assert model_call["model"].provider_key == "openrouter"
    assert model_call["model"].model_key == "openrouter-default"
    assert model_call["provider_model_name"] == "openai/gpt-4o-mini"

    assert trace_recorder.finish_trace_calls, "finish_trace was never invoked"
    finish_call = trace_recorder.finish_trace_calls[-1]
    assert finish_call["provider_key"] == "openrouter"
    assert finish_call["model_key"] == "openrouter-default"
    assert finish_call["provider_model_name"] == "openai/gpt-4o-mini"


def test_rag_orchestrator_defaults_to_mock_when_ai_provider_is_mock(db_session: Session) -> None:
    """Sanity check that development/test behaviour is unchanged: with
    AI_PROVIDER left at its default, an unpinned request still resolves to
    the deterministic mock model exactly as before this change."""
    with _settings_override(
        APP_ENV="test",
        AI_PROVIDER="mock",
        DEFAULT_AI_MODEL_KEY="mock-grounded-answer",
        EMBEDDING_PROVIDER="local-mock",
        EMBEDDING_MODEL="rag-test",
        EMBEDDING_DIMENSION=8,
        RETRIEVAL_MAX_CONTEXT_CHUNKS=5,
        RETRIEVAL_MAX_CONTEXT_CHARS=1000,
        RETRIEVAL_MIN_SIMILARITY_SCORE=0.0,
    ):
        ai_core = create_ai_core()
        organisation_id, workspace_id = _seed_tenant_with_chunk(db_session)
        embedding_provider = LocalMockEmbeddingProvider(dimension=8, model_name="rag-test")

        orchestrator = RAGOrchestrator(RAGOrchestratorDependencies(db=db_session, ai_core=ai_core, embedding_provider=embedding_provider))
        result = orchestrator.answer(
            RAGOrchestrationRequest(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                query="Refunds are available within 30 days of purchase.",
                channel="dashboard_test",
            )
        )

    assert result.provider_key == "mock"
    assert result.model_key == "mock-grounded-answer"
