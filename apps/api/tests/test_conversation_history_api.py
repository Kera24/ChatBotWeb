from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app
from app.repositories.document_repository import (
    create_chunk_for_workspace,
    create_document_for_workspace,
    create_document_version_for_workspace,
)
from app.services.conversation import (
    append_assistant_message,
    append_user_message,
    attach_citations_to_assistant_message,
    start_conversation,
)


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

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

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


def seed_conversation(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    channel: str = "dashboard_test",
    status: str = "active",
    title: str | None = "Admissions chat",
    metadata_json: dict | None = None,
    answer_state: str = "answered",
):
    with client.app.state.testing_session() as db:
        conversation = start_conversation(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            channel=channel,
            title=title,
            metadata_json=metadata_json or {"source": "test"},
        )
        user_message = append_user_message(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            content="When do applications close?",
        )
        assistant_message = append_assistant_message(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            content="Applications close in December.",
            answer_state=answer_state,
            model_key="mock-grounded-answer",
            provider_key="mock",
            provider_model_name="mock-local-v1",
            prompt_key="grounded_rag_answer",
            prompt_version=1,
            prompt_hash="hash-123",
            execution_id="exec-123",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            estimated_cost=Decimal("0.00000000"),
            latency_ms=12,
            finish_reason="stop",
            error_code="AI_PROVIDER_ERROR" if answer_state == "failed" else None,
            metadata_json={
                "provider_metadata": {"secret": "do-not-return"},
                "rendered_prompt": "do-not-return",
            },
        )
        document = create_document_for_workspace(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title="Admissions Handbook",
            source_type="txt",
            source_key=f"{conversation.id}.txt",
        )
        version = create_document_version_for_workspace(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            version_number=1,
            checksum=f"checksum-{conversation.id}",
        )
        chunk = create_chunk_for_workspace(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_index=0,
            content="Applications close in December.",
            content_hash=f"hash-{conversation.id}",
            source_type="txt",
            source_title="Admissions Handbook",
            status="ready",
        )
        citation = attach_citations_to_assistant_message(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            citations=[
                {
                    "chunk_id": chunk.id,
                    "citation_index": 1,
                    "similarity_score": Decimal("0.987654"),
                    "quoted_text": "Applications close in December.",
                }
            ],
        )[0]
        if status != "active":
            conversation.status = status
            if status in {"completed", "archived", "abandoned"}:
                conversation.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(conversation)
        return conversation.id, user_message.id, assistant_message.id, citation.id


def list_conversations(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, role: str, **params):
    query = {"organisation_id": organisation_id}
    query.update(params)
    return client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations",
        params=query,
        headers=dev_headers(email, role),
    )


def get_conversation(client: TestClient, *, organisation_id: str, workspace_id: str, conversation_id: str, email: str, role: str):
    return client.get(
        f"/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}",
        params={"organisation_id": organisation_id},
        headers=dev_headers(email, role),
    )


def test_member_and_viewer_can_list_conversations_in_own_workspace(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    conversation_id, _user_message_id, _assistant_message_id, _citation_id = seed_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id
    )

    response = list_conversations(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["id"] for item in data] == [conversation_id]
    assert data[0]["message_count"] == 2
    assert data[0]["last_message_preview"] == "Applications close in December."
    assert data[0]["metadata"] == {"source": "test"}
    assert "anonymous_user_id" not in data[0]
    assert "external_user_id" not in data[0]


def test_non_member_denied_and_cross_tenant_conversations_not_returned(client: TestClient) -> None:
    org_a, workspace_a, _user_a = seed_tenant(
        client, organisation_name="Alpha", organisation_slug="alpha", user_email="alpha@example.test", role="viewer"
    )
    org_b, workspace_b, _user_b = seed_tenant(
        client, organisation_name="Beta", organisation_slug="beta", user_email="beta@example.test", role="viewer"
    )
    conversation_a, _user_message_id, _assistant_message_id, _citation_id = seed_conversation(
        client, organisation_id=org_a, workspace_id=workspace_a
    )
    conversation_b, _user_message_b, _assistant_message_b, _citation_b = seed_conversation(
        client, organisation_id=org_b, workspace_id=workspace_b
    )

    own_response = list_conversations(
        client, organisation_id=org_a, workspace_id=workspace_a, email="alpha@example.test", role="viewer"
    )
    denied_response = list_conversations(
        client, organisation_id=org_a, workspace_id=workspace_a, email="beta@example.test", role="viewer"
    )

    returned_ids = [item["id"] for item in own_response.json()["data"]]
    assert own_response.status_code == 200
    assert returned_ids == [conversation_a]
    assert conversation_b not in returned_ids
    assert denied_response.status_code == 403


def test_conversation_detail_returns_ordered_messages_citations_and_metadata(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client, organisation_name="Alpha", organisation_slug="alpha", user_email="admin@example.test", role="client_admin"
    )
    conversation_id, user_message_id, assistant_message_id, citation_id = seed_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id
    )

    response = get_conversation(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        email="admin@example.test",
        role="client_admin",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == conversation_id
    assert [message["id"] for message in data["messages"]] == [user_message_id, assistant_message_id]
    assert [message["sequence_number"] for message in data["messages"]] == [1, 2]
    assistant = data["messages"][1]
    assert assistant["answer_state"] == "answered"
    assert assistant["model_key"] == "mock-grounded-answer"
    assert assistant["provider_key"] == "mock"
    assert assistant["provider_model_name"] == "mock-local-v1"
    assert assistant["prompt_key"] == "grounded_rag_answer"
    assert assistant["prompt_hash"] == "hash-123"
    assert assistant["execution_id"] == "exec-123"
    assert assistant["input_tokens"] == 10
    assert assistant["output_tokens"] == 5
    assert assistant["total_tokens"] == 15
    assert Decimal(str(assistant["estimated_cost"])) == Decimal("0E-8")
    assert assistant["latency_ms"] == 12
    assert assistant["finish_reason"] == "stop"
    assert assistant["citations"][0]["id"] == citation_id
    assert assistant["citations"][0]["source_title"] == "Admissions Handbook"
    assert data["messages"][0]["citations"] == []


def test_failed_and_fallback_states_are_returned(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client, organisation_name="Alpha", organisation_slug="alpha", user_email="viewer@example.test", role="viewer"
    )
    failed_id, _u1, _a1, _c1 = seed_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id, answer_state="failed"
    )
    fallback_id, _u2, _a2, _c2 = seed_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id, answer_state="fallback"
    )

    failed = get_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=failed_id, email="viewer@example.test", role="viewer"
    ).json()["data"]
    fallback = get_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=fallback_id, email="viewer@example.test", role="viewer"
    ).json()["data"]

    assert failed["messages"][1]["answer_state"] == "failed"
    assert failed["messages"][1]["error_code"] == "AI_PROVIDER_ERROR"
    assert fallback["messages"][1]["answer_state"] == "fallback"


def test_status_channel_limit_offset_and_max_limit(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client, organisation_name="Alpha", organisation_slug="alpha", user_email="viewer@example.test", role="viewer"
    )
    active_id, _u1, _a1, _c1 = seed_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id, channel="dashboard_test", status="active"
    )
    completed_id, _u2, _a2, _c2 = seed_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id, channel="api", status="completed"
    )

    by_status = list_conversations(
        client, organisation_id=organisation_id, workspace_id=workspace_id, email="viewer@example.test", role="viewer", status="completed"
    )
    by_channel = list_conversations(
        client, organisation_id=organisation_id, workspace_id=workspace_id, email="viewer@example.test", role="viewer", channel="dashboard_test"
    )
    limited = list_conversations(
        client, organisation_id=organisation_id, workspace_id=workspace_id, email="viewer@example.test", role="viewer", limit=1, offset=1
    )
    too_large = list_conversations(
        client, organisation_id=organisation_id, workspace_id=workspace_id, email="viewer@example.test", role="viewer", limit=101
    )

    assert [item["id"] for item in by_status.json()["data"]] == [completed_id]
    assert [item["id"] for item in by_channel.json()["data"]] == [active_id]
    assert limited.status_code == 200
    assert len(limited.json()["data"]) == 1
    assert too_large.status_code == 422


def test_started_date_filters(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client, organisation_name="Alpha", organisation_slug="alpha", user_email="viewer@example.test", role="viewer"
    )
    conversation_id, _u1, _a1, _c1 = seed_conversation(client, organisation_id=organisation_id, workspace_id=workspace_id)
    after = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    before = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    included = list_conversations(
        client, organisation_id=organisation_id, workspace_id=workspace_id, email="viewer@example.test", role="viewer", started_after=after
    )
    excluded = list_conversations(
        client, organisation_id=organisation_id, workspace_id=workspace_id, email="viewer@example.test", role="viewer", started_before=before
    )

    assert [item["id"] for item in included.json()["data"]] == [conversation_id]
    assert excluded.json()["data"] == []


def test_missing_and_cross_tenant_detail_return_safe_404(client: TestClient) -> None:
    org_a, workspace_a, _user_a = seed_tenant(
        client, organisation_name="Alpha", organisation_slug="alpha", user_email="alpha@example.test", role="viewer"
    )
    org_b, workspace_b, _user_b = seed_tenant(
        client, organisation_name="Beta", organisation_slug="beta", user_email="beta@example.test", role="viewer"
    )
    conversation_id, _u, _a, _c = seed_conversation(client, organisation_id=org_a, workspace_id=workspace_a)

    missing = get_conversation(
        client, organisation_id=org_a, workspace_id=workspace_a, conversation_id="missing", email="alpha@example.test", role="viewer"
    )
    cross = get_conversation(
        client, organisation_id=org_b, workspace_id=workspace_b, conversation_id=conversation_id, email="beta@example.test", role="viewer"
    )

    assert missing.status_code == 404
    assert cross.status_code == 404
    assert missing.json()["detail"] == cross.json()["detail"]


def test_response_excludes_system_prompt_secret_and_internal_metadata_fields(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client, organisation_name="Alpha", organisation_slug="alpha", user_email="viewer@example.test", role="viewer"
    )
    conversation_id, _u, _a, _c = seed_conversation(client, organisation_id=organisation_id, workspace_id=workspace_id)

    response = get_conversation(
        client, organisation_id=organisation_id, workspace_id=workspace_id, conversation_id=conversation_id, email="viewer@example.test", role="viewer"
    )

    payload = response.text
    assert "rendered_prompt" not in payload
    assert "system_prompt" not in payload
    assert "user_prompt" not in payload
    assert "provider_metadata" not in payload
    assert "secret" not in payload
    assert "metadata_json" not in payload
    assert "anonymous_user_id" not in payload
    assert "external_user_id" not in payload
