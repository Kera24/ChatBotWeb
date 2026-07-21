from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AuditEvent, ChatMessage, Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app
from app.repositories.document_repository import create_chunk_for_workspace, create_document_for_workspace, create_document_version_for_workspace
from app.services.conversation import append_assistant_message, append_user_message, attach_citations_to_assistant_message, start_conversation


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def headers(email: str, role: str) -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


def seed_tenant(client: TestClient, *, slug: str, email: str, role: str = "client_admin") -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        org = Organisation(name=f"{slug} Org", slug=slug)
        user = User(email=email)
        workspace = Workspace(organisation=org, name="Knowledge", slug=f"{slug}-knowledge")
        membership = Membership(organisation=org, user=user, role=role)
        db.add_all([org, user, workspace, membership])
        db.commit()
        return org.id, workspace.id, user.id


def seed_review_candidate(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    answer_state: str,
    channel: str = "dashboard_test",
    question: str = "What is the refund policy?",
    answer: str = "I do not have enough grounded context to answer.",
    with_citation: bool = True,
) -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        conversation = start_conversation(db, organisation_id=organisation_id, workspace_id=workspace_id, channel=channel, title="Review chat")
        user = append_user_message(db, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=conversation.id, content=question)
        assistant = append_assistant_message(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            content=answer,
            answer_state=answer_state,
            model_key="mock-default",
            provider_key="mock",
            prompt_key="grounded_rag_answer",
            prompt_version=1,
            estimated_cost=Decimal("0.00010000"),
            latency_ms=33,
            error_code="provider_timeout" if answer_state == "failed" else None,
            metadata_json={"rendered_prompt": "do-not-return", "secret": "hidden"},
        )
        if with_citation:
            document = create_document_for_workspace(
                db, organisation_id=organisation_id, workspace_id=workspace_id, title="Refund Guide", source_type="txt", source_key=f"{assistant.id}.txt"
            )
            version = create_document_version_for_workspace(
                db, organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, version_number=1, checksum=f"checksum-{assistant.id}"
            )
            chunk = create_chunk_for_workspace(
                db,
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                document_id=document.id,
                document_version_id=version.id,
                chunk_index=0,
                content="Refunds are processed within five days.",
                content_hash=f"hash-{assistant.id}",
                source_type="txt",
                source_title="Refund Guide",
                status="ready",
            )
            attach_citations_to_assistant_message(
                db,
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                message_id=assistant.id,
                citations=[{"chunk_id": chunk.id, "citation_index": 1, "similarity_score": Decimal("0.900000"), "quoted_text": "Refunds are processed within five days."}],
            )
        db.commit()
        return conversation.id, user.id, assistant.id


def list_review(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, role: str, **params):
    query = {"organisation_id": organisation_id}
    query.update(params)
    return client.get(f"/api/v1/workspaces/{workspace_id}/review/unanswered", params=query, headers=headers(email, role))


def get_review(client: TestClient, *, organisation_id: str, workspace_id: str, message_id: str, email: str, role: str):
    return client.get(f"/api/v1/workspaces/{workspace_id}/review/unanswered/{message_id}", params={"organisation_id": organisation_id}, headers=headers(email, role))


def patch_review(client: TestClient, *, organisation_id: str, workspace_id: str, message_id: str, email: str, role: str, status: str, note: str | None = None):
    return client.patch(
        f"/api/v1/workspaces/{workspace_id}/review/unanswered/{message_id}",
        params={"organisation_id": organisation_id},
        headers=headers(email, role),
        json={"review_status": status, "reviewer_note": note},
    )


def test_fallback_failed_and_low_confidence_appear_answered_excluded(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="admin@example.test")
    _c1, _u1, fallback = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="fallback")
    _c2, _u2, failed = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="failed")
    _c3, _u3, low = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="low_confidence")
    _c4, _u4, answered = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="answered")

    response = list_review(client, organisation_id=org, workspace_id=workspace, email="admin@example.test", role="client_admin")

    assert response.status_code == 200
    ids = {item["assistant_message_id"] for item in response.json()["data"]}
    assert {fallback, failed, low}.issubset(ids)
    assert answered not in ids
    assert response.json()["meta"]["total"] == 3


def test_filters_pagination_limit_and_user_question_pairing(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="viewer@example.test", role="viewer")
    _c1, _u1, fallback = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="fallback", channel="dashboard_test", question="Question A?")
    _c2, _u2, _failed = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="failed", channel="api", question="Question B?")
    after = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    by_state = list_review(client, organisation_id=org, workspace_id=workspace, email="viewer@example.test", role="viewer", answer_state="fallback")
    by_channel = list_review(client, organisation_id=org, workspace_id=workspace, email="viewer@example.test", role="viewer", channel="api")
    paged = list_review(client, organisation_id=org, workspace_id=workspace, email="viewer@example.test", role="viewer", limit=1, offset=1)
    dated = list_review(client, organisation_id=org, workspace_id=workspace, email="viewer@example.test", role="viewer", created_after=after)
    too_large = list_review(client, organisation_id=org, workspace_id=workspace, email="viewer@example.test", role="viewer", limit=101)

    assert [item["assistant_message_id"] for item in by_state.json()["data"]] == [fallback]
    assert by_state.json()["data"][0]["user_question"] == "Question A?"
    assert by_channel.json()["data"][0]["channel"] == "api"
    assert paged.status_code == 200 and len(paged.json()["data"]) == 1
    assert dated.json()["meta"]["total"] == 2
    assert too_large.status_code == 422


def test_detail_returns_citations_context_and_excludes_private_metadata(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="viewer@example.test", role="viewer")
    conversation_id, user_id, assistant_id = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="failed")

    response = get_review(client, organisation_id=org, workspace_id=workspace, message_id=assistant_id, email="viewer@example.test", role="viewer")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["item"]["conversation_id"] == conversation_id
    assert data["item"]["assistant_message_id"] == assistant_id
    assert data["item"]["error_code"] == "provider_timeout"
    assert data["item"]["citations"][0]["source_title"] == "Refund Guide"
    assert [message["id"] for message in data["conversation_context"]] == [user_id, assistant_id]
    payload = response.text
    assert "rendered_prompt" not in payload
    assert "secret" not in payload
    assert "metadata_json" not in payload


def test_tenant_isolation_and_non_member_denied(client: TestClient) -> None:
    org_a, workspace_a, _ = seed_tenant(client, slug="alpha", email="alpha@example.test", role="viewer")
    org_b, workspace_b, _ = seed_tenant(client, slug="beta", email="beta@example.test", role="viewer")
    _conversation_id, _user_id, assistant_id = seed_review_candidate(client, organisation_id=org_a, workspace_id=workspace_a, answer_state="fallback")

    own = list_review(client, organisation_id=org_a, workspace_id=workspace_a, email="alpha@example.test", role="viewer")
    denied = list_review(client, organisation_id=org_a, workspace_id=workspace_a, email="beta@example.test", role="viewer")
    cross = get_review(client, organisation_id=org_b, workspace_id=workspace_b, message_id=assistant_id, email="beta@example.test", role="viewer")

    assert own.status_code == 200 and own.json()["data"][0]["assistant_message_id"] == assistant_id
    assert denied.status_code == 403
    assert cross.status_code == 404


def test_admin_update_review_status_creates_audit_and_preserves_content(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test", role="client_admin")
    _conversation_id, _user_id, assistant_id = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="low_confidence", answer="Original assistant answer")

    response = patch_review(
        client,
        organisation_id=org,
        workspace_id=workspace,
        message_id=assistant_id,
        email="admin@example.test",
        role="client_admin",
        status="knowledge_gap",
        note="Add a clearer refund article.",
    )

    assert response.status_code == 200
    item = response.json()["data"]
    assert item["review_status"] == "knowledge_gap"
    assert item["reviewer_note"] == "Add a clearer refund article."
    with client.app.state.testing_session() as db:
        message = db.execute(select(ChatMessage).where(ChatMessage.id == assistant_id)).scalar_one()
        events = db.execute(select(AuditEvent).where(AuditEvent.entity_id == assistant_id)).scalars().all()
    assert message.content == "Original assistant answer"
    assert len(events) == 1
    assert events[0].action == "review.status.changed"
    assert events[0].previous_status == "open"
    assert events[0].new_status == "knowledge_gap"
    assert events[0].actor_user_id == user_id


def test_viewer_cannot_update_and_invalid_status_rejected(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="viewer@example.test", role="viewer")
    _conversation_id, _user_id, assistant_id = seed_review_candidate(client, organisation_id=org, workspace_id=workspace, answer_state="fallback")

    viewer = patch_review(client, organisation_id=org, workspace_id=workspace, message_id=assistant_id, email="viewer@example.test", role="viewer", status="reviewed")
    admin_invalid = patch_review(client, organisation_id=org, workspace_id=workspace, message_id=assistant_id, email="viewer@example.test", role="super_admin", status="not-a-status")

    assert viewer.status_code == 403
    assert admin_invalid.status_code == 422
