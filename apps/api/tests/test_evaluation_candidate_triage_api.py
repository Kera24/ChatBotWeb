from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import AITrace, Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app


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


def seed_tenant(client: TestClient, *, slug: str) -> dict[str, str]:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active")
        owner = User(email=f"owner-{unique}@example.test")
        viewer = User(email=f"viewer-{unique}@example.test")
        workspace = Workspace(organisation=org, name="Workspace", slug=f"{slug}-workspace-{unique}", status="active")
        db.add_all([
            org, owner, viewer, workspace,
            Membership(organisation=org, user=owner, role="org_owner", status="active"),
            Membership(organisation=org, user=viewer, role="viewer", status="active"),
        ])
        db.commit()
        widget = create_widget(
            db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=owner.id
        )
        return {"organisation_id": org.id, "workspace_id": workspace.id, "widget_id": widget.id, "owner_email": owner.email, "viewer_email": viewer.email}


def create_candidate_api(client: TestClient, tenant: dict[str, str], *, question: str = "Where is my order?") -> dict:
    response = client.post(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"widget_id": tenant["widget_id"], "signal_type": "manual_selection", "severity": "medium", "question": question},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_viewer_can_read_but_not_triage(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-rbac")
    candidate = create_candidate_api(client, tenant)

    read_response = client.get(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{candidate['id']}",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["viewer_email"], "viewer"),
    )
    assert read_response.status_code == 200

    triage_response = client.patch(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{candidate['id']}",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["viewer_email"], "viewer"),
        json={"triage_status": "triaged"},
    )
    assert triage_response.status_code == 403


def test_invalid_triage_status_is_rejected(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-invalid")
    candidate = create_candidate_api(client, tenant)

    response = client.patch(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{candidate['id']}",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"triage_status": "not_a_real_status"},
    )
    assert response.status_code == 422


def test_terminal_status_cannot_be_moved_again(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-terminal")
    candidate = create_candidate_api(client, tenant)

    rejected = client.patch(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{candidate['id']}",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"triage_status": "rejected"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["triage_status"] == "rejected"
    assert rejected.json()["data"]["resolved_at"] is not None

    reopen_attempt = client.patch(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{candidate['id']}",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"triage_status": "accepted"},
    )
    assert reopen_attempt.status_code == 422


def test_first_triage_transition_sets_first_triaged_at(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-timestamp")
    candidate = create_candidate_api(client, tenant)
    assert candidate["first_triaged_at"] is None

    response = client.patch(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{candidate['id']}",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"triage_status": "triaged", "root_cause_category": "answerable_factual"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["first_triaged_at"] is not None
    assert data["root_cause_category"] == "answerable_factual"


def test_mark_duplicate_requires_existing_target(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-dup")
    candidate = create_candidate_api(client, tenant)

    response = client.post(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{candidate['id']}/mark-duplicate",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"duplicate_of_id": "does-not-exist"},
    )
    assert response.status_code == 422


def test_create_candidate_resolves_public_trace_id_to_internal_id(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-trace-link")
    public_trace_id = str(uuid4())
    with client.app.state.testing_session() as db:
        trace = AITrace(
            trace_id=public_trace_id, organisation_id=tenant["organisation_id"], workspace_id=tenant["workspace_id"],
            assistant_id=tenant["widget_id"], channel="widget", created_at=datetime.now(timezone.utc),
        )
        db.add(trace)
        db.commit()
        internal_trace_id = trace.id

    created = client.post(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"widget_id": tenant["widget_id"], "signal_type": "manual_selection", "severity": "medium", "question": "Linked to a trace", "source_trace_id": public_trace_id},
    )
    assert created.status_code == 201
    assert created.json()["data"]["source_trace_id"] == internal_trace_id

    detail = client.get(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{created.json()['data']['id']}",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["source_trace_public_id"] == public_trace_id


def test_create_candidate_rejects_unknown_trace_id(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-trace-missing")
    response = client.post(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"widget_id": tenant["widget_id"], "signal_type": "manual_selection", "severity": "medium", "question": "q", "source_trace_id": "does-not-exist"},
    )
    assert response.status_code == 422


def test_mark_duplicate_succeeds_against_existing_candidate(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="triage-dup-ok")
    original = create_candidate_api(client, tenant, question="How do I get a refund?")
    duplicate = create_candidate_api(client, tenant, question="Can you refund my order?")

    response = client.post(
        f"/api/v1/workspaces/{tenant['workspace_id']}/evaluation-candidates/{duplicate['id']}/mark-duplicate",
        params={"organisation_id": tenant["organisation_id"]},
        headers=headers(tenant["owner_email"], "org_owner"),
        json={"duplicate_of_id": original["id"]},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["triage_status"] == "duplicate"
    assert data["duplicate_of_id"] == original["id"]
