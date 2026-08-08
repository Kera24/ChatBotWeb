from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app
from app.repositories import evaluation_candidate_repository


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


def seed_tenant(client: TestClient, *, slug: str) -> tuple[str, str, str, str]:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active")
        user = User(email=f"owner-{slug}-{unique}@example.test")
        workspace = Workspace(organisation=org, name="Workspace", slug=f"{slug}-workspace-{unique}", status="active")
        membership = Membership(organisation=org, user=user, role="org_owner", status="active")
        db.add_all([org, user, workspace, membership])
        db.commit()
        widget = create_widget(
            db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id
        )
        return org.id, workspace.id, widget.id, user.email


def test_repository_get_candidate_is_scoped_to_organisation_and_workspace(client: TestClient) -> None:
    org_a, workspace_a, widget_a, _ = seed_tenant(client, slug="tenant-a")
    org_b, workspace_b, _widget_b, _ = seed_tenant(client, slug="tenant-b")
    with client.app.state.testing_session() as db:
        candidate = evaluation_candidate_repository.create_candidate(
            db,
            organisation_id=org_a,
            workspace_id=workspace_a,
            widget_id=widget_a,
            signal_type="fallback",
            severity="medium",
            question="Where is my invoice?",
            response=None,
            reason_code="fallback",
        )

        assert evaluation_candidate_repository.get_candidate(db, organisation_id=org_b, workspace_id=workspace_b, candidate_id=candidate.id) is None
        assert evaluation_candidate_repository.get_candidate(db, organisation_id=org_a, workspace_id=workspace_b, candidate_id=candidate.id) is None
        assert evaluation_candidate_repository.get_candidate(db, organisation_id=org_a, workspace_id=workspace_a, candidate_id=candidate.id) is not None


def test_api_returns_404_not_403_for_cross_tenant_candidate_access(client: TestClient) -> None:
    org_a, workspace_a, widget_a, owner_a = seed_tenant(client, slug="api-tenant-a")
    org_b, workspace_b, _widget_b, owner_b = seed_tenant(client, slug="api-tenant-b")

    created = client.post(
        f"/api/v1/workspaces/{workspace_a}/evaluation-candidates",
        params={"organisation_id": org_a},
        headers=headers(owner_a, "org_owner"),
        json={"widget_id": widget_a, "signal_type": "manual_selection", "severity": "medium", "question": "Where is my invoice?"},
    )
    assert created.status_code == 201
    candidate_id = created.json()["data"]["id"]

    cross_tenant_response = client.get(
        f"/api/v1/workspaces/{workspace_b}/evaluation-candidates/{candidate_id}",
        params={"organisation_id": org_b},
        headers=headers(owner_b, "org_owner"),
    )
    assert cross_tenant_response.status_code == 404


def test_list_candidates_does_not_leak_across_organisations(client: TestClient) -> None:
    org_a, workspace_a, widget_a, owner_a = seed_tenant(client, slug="list-tenant-a")
    org_b, workspace_b, widget_b, owner_b = seed_tenant(client, slug="list-tenant-b")

    with client.app.state.testing_session() as db:
        evaluation_candidate_repository.create_candidate(
            db, organisation_id=org_a, workspace_id=workspace_a, widget_id=widget_a, signal_type="fallback", severity="medium",
            question="A question in tenant A", response=None, reason_code="fallback",
        )
        evaluation_candidate_repository.create_candidate(
            db, organisation_id=org_b, workspace_id=workspace_b, widget_id=widget_b, signal_type="fallback", severity="medium",
            question="A question in tenant B", response=None, reason_code="fallback",
        )

    response = client.get(
        f"/api/v1/workspaces/{workspace_a}/evaluation-candidates",
        params={"organisation_id": org_a},
        headers=headers(owner_a, "org_owner"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["redacted_question"] == "A question in tenant A"
