from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.db.models import ChatMessage, ChatSession, Chunk, Document, DocumentVersion, PublicCredential, PublicMessageRequest, PublicSession
from test_public_widget_session_endpoint import client, post_session, seed_widget

ORIGIN = "http://localhost:3000"


def create_public_session(client: TestClient, public_key: str) -> str:
    response = post_session(client, public_key, origin=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()["session_token"]


def post_message(client: TestClient, public_key: str, token: str, *, message: str = "What are the admissions dates?", key: str = "idem-message-123456", origin: str | None = ORIGIN, extra_body: dict | None = None):
    headers = {"Content-Type": "application/json", "Idempotency-Key": key, "X-Request-ID": f"req-{key}"}
    if origin is not None:
        headers["Origin"] = origin
    body = {"session_token": token, "message": message}
    if extra_body:
        body.update(extra_body)
    return client.post(f"/api/v1/widget/{public_key}/messages", headers=headers, json=body)


def add_embedded_chunk_for_public_key(client: TestClient, public_key: str, *, content: str = "applications close in december", title: str = "Admissions Handbook") -> None:
    with client.app.state.testing_session() as db:
        credential = db.execute(select(PublicCredential).where(PublicCredential.public_identifier == public_key)).scalar_one()
        document = Document(
            organisation_id=credential.organisation_id,
            workspace_id=credential.workspace_id,
            title=title,
            source_type="txt",
            source_key=f"{title}.txt",
            status="ready",
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            organisation_id=credential.organisation_id,
            workspace_id=credential.workspace_id,
            document_id=document.id,
            version_number=1,
            checksum=f"checksum-{title}",
            processing_status="ready",
        )
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id
        db.add(
            Chunk(
                organisation_id=credential.organisation_id,
                workspace_id=credential.workspace_id,
                document_id=document.id,
                document_version_id=version.id,
                chunk_index=0,
                content=content,
                content_hash=f"hash-{title}",
                token_count=len(content.split()),
                source_type="txt",
                source_title=title,
                page_number=1,
                section_title="Admissions",
                status="ready",
                embedding_provider="local-mock",
                embedding_model=settings.EMBEDDING_MODEL,
                embedding_dimension=settings.EMBEDDING_DIMENSION,
                embedding_created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()


def configure_rag_settings(_monkeypatch) -> None:
    # Settings are frozen dataclass values; use the repository defaults and seed matching chunk metadata.
    return None


def test_public_widget_message_fallback_completes_idempotency_and_persists_messages(client: TestClient, monkeypatch) -> None:
    configure_rag_settings(monkeypatch)
    public_key = seed_widget(client)
    token = create_public_session(client, public_key)

    response = post_message(client, public_key, token, message="No matching knowledge exists")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response_id"].startswith("pmr_")
    assert body["answer_state"] == "fallback"
    assert body["fallback_used"] is True
    assert body["citations"] == []
    assert body["remaining_messages"] == 29
    for excluded in ("organisation_id", "workspace_id", "conversation_id", "assistant_message_id", "execution_id", "model_key", "prompt_key", "token_usage"):
        assert excluded not in body
    with client.app.state.testing_session() as db:
        session = db.execute(select(PublicSession)).scalar_one()
        assert session.message_count == 1
        assert session.conversation_id is not None
        messages = db.execute(select(ChatMessage).where(ChatMessage.conversation_id == session.conversation_id).order_by(ChatMessage.sequence_number)).scalars().all()
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[1].answer_state == "fallback"
        record = db.execute(select(PublicMessageRequest)).scalar_one()
        assert record.status == "completed"
        assert record.response_snapshot_json == body


def test_completed_duplicate_returns_snapshot_without_new_messages_or_slot(client: TestClient, monkeypatch) -> None:
    configure_rag_settings(monkeypatch)
    public_key = seed_widget(client)
    token = create_public_session(client, public_key)

    first = post_message(client, public_key, token, key="idem-duplicate-123456")
    second = post_message(client, public_key, token, key="idem-duplicate-123456")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    with client.app.state.testing_session() as db:
        session = db.execute(select(PublicSession)).scalar_one()
        assert session.message_count == 1
        messages = db.execute(select(ChatMessage)).scalars().all()
        assert len(messages) == 2


def test_grounded_answer_projects_safe_citations_and_reuses_conversation(client: TestClient, monkeypatch) -> None:
    configure_rag_settings(monkeypatch)
    public_key = seed_widget(client)
    add_embedded_chunk_for_public_key(client, public_key, content="applications close in december", title="Admissions Handbook")
    token = create_public_session(client, public_key)

    first = post_message(client, public_key, token, message="applications close in december", key="idem-grounded-123456")
    second = post_message(client, public_key, token, message="applications close in december", key="idem-grounded-abcdef")

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["answer_state"] == "answered"
    assert body["fallback_used"] is False
    assert body["citations"][0]["source_title"] == "Admissions Handbook"
    assert "chunk_id" not in str(body)
    assert "similarity_score" not in str(body)
    assert second.status_code == 200
    with client.app.state.testing_session() as db:
        sessions = db.execute(select(ChatSession)).scalars().all()
        assert len(sessions) == 1
        messages = db.execute(select(ChatMessage).order_by(ChatMessage.sequence_number)).scalars().all()
        assert [message.role for message in messages] == ["user", "assistant", "user", "assistant"]


def test_message_route_rejects_missing_idempotency_forbidden_fields_and_dashboard_headers(client: TestClient) -> None:
    public_key = seed_widget(client)
    token = create_public_session(client, public_key)

    missing_key = client.post(f"/api/v1/widget/{public_key}/messages", headers={"Content-Type": "application/json", "Origin": ORIGIN}, json={"session_token": token, "message": "hello"})
    forbidden = post_message(client, public_key, token, extra_body={"organisation_id": "org-1", "model_key": "client-choice"})
    dashboard = post_message(client, public_key, token, key="idem-dashboard-123456", extra_body=None)
    dashboard = client.post(
        f"/api/v1/widget/{public_key}/messages",
        headers={"Content-Type": "application/json", "Origin": ORIGIN, "Idempotency-Key": "idem-dashboard-123456", "X-Development-User-Email": "admin@example.test"},
        json={"session_token": token, "message": "hello"},
    )

    assert missing_key.status_code == 400
    assert missing_key.json()["error"]["code"] == "idempotency_key_required"
    assert forbidden.status_code == 400
    assert forbidden.json()["error"]["code"] == "invalid_request"
    assert dashboard.status_code == 400
    assert dashboard.json()["error"]["code"] == "invalid_request"


def test_message_preflight_cors_and_origin_denial(client: TestClient) -> None:
    public_key = seed_widget(client)

    allowed = client.options(f"/api/v1/widget/{public_key}/messages", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"})
    denied = client.options(f"/api/v1/widget/{public_key}/messages", headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"})

    assert allowed.status_code == 204
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert "Idempotency-Key" in allowed.headers["access-control-allow-headers"]
    assert allowed.headers["access-control-allow-credentials"] == "false"
    assert denied.status_code == 403
    assert "access-control-allow-origin" not in denied.headers


def test_invalid_session_and_origin_rejected_before_rag(client: TestClient) -> None:
    public_key = seed_widget(client)
    token = create_public_session(client, public_key)

    bad_session = post_message(client, public_key, "pss_dev_invalid.invalid", key="idem-invalid-123456")
    bad_origin = post_message(client, public_key, token, key="idem-origin-123456", origin="http://evil.test")

    assert bad_session.status_code == 401
    assert bad_session.json()["error"]["code"] == "invalid_session"
    assert bad_origin.status_code == 403
    assert bad_origin.json()["error"]["code"] == "origin_not_allowed"
    with client.app.state.testing_session() as db:
        messages = db.execute(select(ChatMessage)).scalars().all()
        assert messages == []
