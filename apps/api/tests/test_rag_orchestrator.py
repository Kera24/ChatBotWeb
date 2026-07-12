from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.rag_orchestrator import RAGOrchestrationRequest, RAGOrchestrator, RAGOrchestratorDependencies, RAGProviderExecutionError
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app
from app.repositories.conversation_repository import list_citations_for_message, list_messages
from app.services.embeddings import build_embedding_provider


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    original_chunks = settings.RETRIEVAL_MAX_CONTEXT_CHUNKS
    original_chars = settings.RETRIEVAL_MAX_CONTEXT_CHARS
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "rag-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHUNKS", 5)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHARS", 1000)

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHUNKS", original_chunks)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHARS", original_chars)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def dev_headers(email: str, role: str) -> dict[str, str]:
    return {
        "X-Development-User-Email": email,
        "X-Development-Role": role,
    }


def seed_tenant(
    client: TestClient,
    *,
    organisation_name: str,
    organisation_slug: str,
    user_email: str,
    role: str,
) -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        organisation = Organisation(name=organisation_name, slug=organisation_slug)
        user = User(email=user_email)
        workspace = Workspace(organisation=organisation, name="Knowledge Base", slug=f"{organisation_slug}-knowledge")
        membership = Membership(organisation=organisation, user=user, role=role)
        db.add_all([organisation, user, workspace, membership])
        db.commit()
        return organisation.id, workspace.id, user.id


def add_embedded_chunk(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    content: str,
    title: str,
    chunk_index: int = 0,
) -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        document = Document(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=title,
            source_type="txt",
            source_key=f"{title}-{chunk_index}.txt",
            status="ready",
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            version_number=1,
            checksum=f"checksum-{title}-{chunk_index}",
            processing_status="ready",
        )
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id
        chunk = Chunk(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_index=chunk_index,
            content=content,
            content_hash=f"hash-{title}-{chunk_index}",
            token_count=len(content.split()),
            source_type="txt",
            source_title=title,
            page_number=chunk_index + 1,
            section_title="Admissions",
            status="ready",
            embedding_provider="local-mock",
            embedding_model="rag-test",
            embedding_dimension=8,
            embedding_created_at=datetime.now(timezone.utc),
        )
        db.add(chunk)
        db.commit()
        return document.id, version.id, chunk.id


def rag_answer(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    email: str,
    role: str,
    query: str,
    conversation_id: str | None = None,
    retrieval_limit: int | None = None,
    max_context_chars: int | None = None,
):
    body: dict[str, object] = {"query": query}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    if retrieval_limit is not None:
        body["retrieval_limit"] = retrieval_limit
    if max_context_chars is not None:
        body["max_context_chars"] = max_context_chars
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/rag/answer",
        params={"organisation_id": organisation_id},
        json=body,
        headers=dev_headers(email, role),
    )


def test_new_conversation_created_and_grounded_answer_persisted(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    _document_id, _version_id, chunk_id = add_embedded_chunk(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        content="applications close in december",
        title="Admissions Handbook",
    )

    response = rag_answer(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="applications close in december",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["conversation_id"]
    assert data["user_message_id"]
    assert data["assistant_message_id"]
    assert data["answer"].startswith("[mock:")
    assert data["answer_state"] == "answered"
    assert data["fallback_used"] is False
    assert data["retrieved_chunk_count"] == 1
    assert data["citations"][0]["chunk_id"] == chunk_id
    assert data["provider_key"] == "mock"
    assert data["model_key"] == "mock-grounded-answer"
    assert data["prompt_key"] == "grounded_rag_answer"
    assert data["token_usage"]["total_tokens"] > 0

    with client.app.state.testing_session() as db:
        messages = list_messages(db, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=data["conversation_id"])
        citations = list_citations_for_message(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            conversation_id=data["conversation_id"],
            message_id=data["assistant_message_id"],
        )
        assert [message.role for message in messages] == ["user", "assistant"]
        assert [message.sequence_number for message in messages] == [1, 2]
        assert messages[1].execution_id == data["execution_id"]
        assert messages[1].total_tokens == data["token_usage"]["total_tokens"]
        assert messages[1].estimated_cost == 0
        assert messages[1].latency_ms == data["latency_ms"]
        assert messages[1].conversation.last_message_at == messages[1].created_at
        assert len(citations) == 1


def test_existing_conversation_reused_and_no_duplicate_assistant(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    add_embedded_chunk(client, organisation_id=organisation_id, workspace_id=workspace_id, content="orientation is monday", title="Guide")

    first = rag_answer(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="orientation is monday",
    ).json()["data"]
    second_response = rag_answer(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="orientation is monday",
        conversation_id=first["conversation_id"],
    )

    assert second_response.status_code == 200
    second = second_response.json()["data"]
    assert second["conversation_id"] == first["conversation_id"]
    with client.app.state.testing_session() as db:
        messages = list_messages(db, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=first["conversation_id"])
        assert [message.sequence_number for message in messages] == [1, 2, 3, 4]
        assert len([message for message in messages if message.role == "assistant"]) == 2
        assert len({message.id for message in messages if message.role == "assistant"}) == 2


def test_cross_tenant_chunks_never_used_and_conversation_rejected(client: TestClient) -> None:
    org_a, workspace_a, _user_a = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha@example.test",
        role="viewer",
    )
    org_b, workspace_b, _user_b = seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta@example.test",
        role="viewer",
    )
    _doc_a, _version_a, chunk_a = add_embedded_chunk(client, organisation_id=org_a, workspace_id=workspace_a, content="shared context", title="Alpha Source")
    _doc_b, _version_b, chunk_b = add_embedded_chunk(client, organisation_id=org_b, workspace_id=workspace_b, content="shared context", title="Beta Source")

    alpha_response = rag_answer(
        client,
        organisation_id=org_a,
        workspace_id=workspace_a,
        email="alpha@example.test",
        role="viewer",
        query="shared context",
    )
    alpha_data = alpha_response.json()["data"]
    returned_chunks = [citation["chunk_id"] for citation in alpha_data["citations"]]

    assert returned_chunks == [chunk_a]
    assert chunk_b not in returned_chunks

    cross_response = rag_answer(
        client,
        organisation_id=org_b,
        workspace_id=workspace_b,
        email="beta@example.test",
        role="viewer",
        query="shared context",
        conversation_id=alpha_data["conversation_id"],
    )
    assert cross_response.status_code == 404


def test_non_member_denied_and_viewer_allowed(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-viewer@example.test",
        role="viewer",
    )
    seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-viewer@example.test",
        role="viewer",
    )
    add_embedded_chunk(client, organisation_id=organisation_id, workspace_id=workspace_id, content="applications close", title="Alpha")

    viewer_response = rag_answer(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="alpha-viewer@example.test",
        role="viewer",
        query="applications close",
    )
    non_member_response = rag_answer(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="beta-viewer@example.test",
        role="viewer",
        query="applications close",
    )

    assert viewer_response.status_code == 200
    assert non_member_response.status_code == 403


def test_empty_retrieval_produces_fallback_and_zero_citations(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = rag_answer(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="nothing indexed",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer_state"] == "fallback"
    assert data["fallback_used"] is True
    assert data["citations"] == []
    assert data["retrieved_chunk_count"] == 0
    with client.app.state.testing_session() as db:
        messages = list_messages(db, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=data["conversation_id"])
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[1].answer_state == "fallback"


def test_retrieval_and_context_limits_respected(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    add_embedded_chunk(client, organisation_id=organisation_id, workspace_id=workspace_id, content="applications " * 40, title="Source A", chunk_index=0)
    add_embedded_chunk(client, organisation_id=organisation_id, workspace_id=workspace_id, content="applications also include interviews", title="Source B", chunk_index=1)

    response = rag_answer(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="applications",
        retrieval_limit=1,
        max_context_chars=90,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["retrieved_chunk_count"] == 1
    assert len(data["citations"]) == 1
    assert len(data["citations"][0]["quoted_text"]) < len("applications " * 40)


def test_provider_failure_and_timeout_preserve_failed_assistant_state(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    add_embedded_chunk(client, organisation_id=organisation_id, workspace_id=workspace_id, content="applications close", title="Alpha")

    with client.app.state.testing_session() as db:
        orchestrator = RAGOrchestrator(
            RAGOrchestratorDependencies(
                db=db,
                ai_core=client.app.state.ai_core,
                embedding_provider=build_embedding_provider(provider_name="local-mock", model_name="rag-test", dimension=8),
            )
        )
        with pytest.raises(RAGProviderExecutionError) as failure:
            orchestrator.answer(
                RAGOrchestrationRequest(
                    organisation_id=organisation_id,
                    workspace_id=workspace_id,
                    query="applications close",
                    simulate_failure=True,
                )
            )
        messages = list_messages(db, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=messages_conversation_id(db, organisation_id, workspace_id))
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[1].answer_state == "failed"
        assert messages[1].error_code == "AI_PROVIDER_ERROR"
        assert messages[1].execution_id == failure.value.execution_id
        assert len([message for message in messages if message.role == "assistant"]) == 1

        with pytest.raises(RAGProviderExecutionError) as timeout:
            orchestrator.answer(
                RAGOrchestrationRequest(
                    organisation_id=organisation_id,
                    workspace_id=workspace_id,
                    query="applications close",
                    simulate_timeout=True,
                )
            )
        assert "TIMEOUT" in timeout.value.provider_error_code


def messages_conversation_id(db: Session, organisation_id: str, workspace_id: str) -> str:
    from app.repositories.conversation_repository import list_conversations

    conversations = list_conversations(db, organisation_id=organisation_id, workspace_id=workspace_id, limit=10)
    return conversations[-1].id
