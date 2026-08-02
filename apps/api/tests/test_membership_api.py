from fastapi.testclient import TestClient

from app.db.models import AuditEvent, Membership, Organisation, User, Workspace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


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

def headers(email: str, role: str = "client_admin") -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


def seed_tenant(client: TestClient, *, slug: str = "alpha") -> tuple[str, str, dict[str, str]]:
    with client.app.state.testing_session() as db:
        org = Organisation(name=f"{slug.title()} College", slug=slug)
        workspace = Workspace(organisation=org, name="Admissions Assistant", slug="admissions")
        owner = User(email=f"owner-{slug}@example.test", full_name="Owner User")
        admin = User(email=f"admin-{slug}@example.test", full_name="Admin User")
        viewer = User(email=f"viewer-{slug}@example.test", full_name="Viewer User")
        inactive = User(email=f"inactive-{slug}@example.test", full_name="Inactive User")
        memberships = [
            Membership(organisation=org, user=owner, role="org_owner", status="active"),
            Membership(organisation=org, user=admin, role="client_admin", status="active"),
            Membership(organisation=org, user=viewer, role="viewer", status="active"),
            Membership(organisation=org, user=inactive, role="contributor", status="inactive"),
        ]
        db.add_all([org, workspace, owner, admin, viewer, inactive, *memberships])
        db.commit()
        return org.id, workspace.id, {membership.user.email: membership.id for membership in memberships}


def list_memberships(client: TestClient, *, org_id: str, workspace_id: str, email: str, role: str = "client_admin"):
    return client.get(f"/api/v1/workspaces/{workspace_id}/memberships", params={"organisation_id": org_id}, headers=headers(email, role))


def patch_role(client: TestClient, *, org_id: str, workspace_id: str, membership_id: str, email: str, role: str = "client_admin", new_role: str = "viewer"):
    return client.patch(
        f"/api/v1/workspaces/{workspace_id}/memberships/{membership_id}/role",
        params={"organisation_id": org_id},
        headers=headers(email, role),
        json={"role": new_role},
    )


def patch_status(client: TestClient, *, org_id: str, workspace_id: str, membership_id: str, email: str, role: str = "client_admin", new_status: str = "inactive"):
    return client.patch(
        f"/api/v1/workspaces/{workspace_id}/memberships/{membership_id}/status",
        params={"organisation_id": org_id},
        headers=headers(email, role),
        json={"status": new_status},
    )


def test_membership_list_is_tenant_scoped_and_viewer_readable(client: TestClient) -> None:
    org_id, workspace_id, _memberships = seed_tenant(client)

    response = list_memberships(client, org_id=org_id, workspace_id=workspace_id, email="viewer-alpha@example.test", role="viewer")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 4
    assert "client_admin" in payload["meta"]["roles"]
    assert {item["user"]["email"] for item in payload["data"]} == {
        "owner-alpha@example.test",
        "admin-alpha@example.test",
        "viewer-alpha@example.test",
        "inactive-alpha@example.test",
    }
    assert payload["data"][0]["workspace_id"] == workspace_id


def test_membership_cross_tenant_denied(client: TestClient) -> None:
    org_a, workspace_a, _ = seed_tenant(client, slug="alpha")
    seed_tenant(client, slug="beta")

    response = list_memberships(client, org_id=org_a, workspace_id=workspace_a, email="admin-beta@example.test", role="client_admin")

    assert response.status_code == 403


def test_membership_role_update_is_rbac_protected_and_audited(client: TestClient) -> None:
    org_id, workspace_id, memberships = seed_tenant(client)

    viewer_denied = patch_role(client, org_id=org_id, workspace_id=workspace_id, membership_id=memberships["viewer-alpha@example.test"], email="viewer-alpha@example.test", role="viewer", new_role="contributor")
    assert viewer_denied.status_code == 403

    response = patch_role(client, org_id=org_id, workspace_id=workspace_id, membership_id=memberships["viewer-alpha@example.test"], email="admin-alpha@example.test", new_role="contributor")
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "contributor"

    with client.app.state.testing_session() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == "membership.role.updated").all()
        assert len(events) == 1
        assert events[0].previous_status == "viewer"
        assert events[0].new_status == "contributor"


def test_membership_status_update_prevents_self_deactivation_and_audits(client: TestClient) -> None:
    org_id, workspace_id, memberships = seed_tenant(client)

    self_deactivate = patch_status(client, org_id=org_id, workspace_id=workspace_id, membership_id=memberships["admin-alpha@example.test"], email="admin-alpha@example.test")
    assert self_deactivate.status_code == 409

    response = patch_status(client, org_id=org_id, workspace_id=workspace_id, membership_id=memberships["viewer-alpha@example.test"], email="admin-alpha@example.test")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "inactive"

    with client.app.state.testing_session() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == "membership.status.updated").all()
        assert len(events) == 1
        assert events[0].previous_status == "active"
        assert events[0].new_status == "inactive"


def test_membership_invalid_role_and_wrong_workspace_rejected(client: TestClient) -> None:
    org_id, workspace_id, memberships = seed_tenant(client, slug="alpha")
    other_org, other_workspace, _ = seed_tenant(client, slug="beta")

    invalid_role = patch_role(client, org_id=org_id, workspace_id=workspace_id, membership_id=memberships["viewer-alpha@example.test"], email="admin-alpha@example.test", new_role="super_admin")
    assert invalid_role.status_code == 422

    wrong_workspace = list_memberships(client, org_id=org_id, workspace_id=other_workspace, email="admin-alpha@example.test")
    assert wrong_workspace.status_code == 404

