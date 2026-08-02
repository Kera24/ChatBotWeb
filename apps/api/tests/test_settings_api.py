from fastapi.testclient import TestClient

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AuditEvent, Membership, Organisation, User, Workspace
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


def seed_settings_tenant(client: TestClient, *, slug: str = "alpha") -> tuple[str, str]:
    with client.app.state.testing_session() as db:
        org = Organisation(name=f"{slug.title()} Organisation", slug=slug, plan_key="pilot")
        workspace = Workspace(organisation=org, name=f"{slug.title()} Workspace", slug=f"{slug}-workspace", default_language="en")
        owner = User(email=f"owner-{slug}@example.test", full_name="Owner User")
        admin = User(email=f"admin-{slug}@example.test", full_name="Admin User")
        contributor = User(email=f"contributor-{slug}@example.test", full_name="Contributor User")
        viewer = User(email=f"viewer-{slug}@example.test", full_name="Viewer User")
        inactive = User(email=f"inactive-{slug}@example.test", full_name="Inactive User")
        db.add_all([
            org,
            workspace,
            owner,
            admin,
            contributor,
            viewer,
            inactive,
            Membership(organisation=org, user=owner, role="org_owner", status="active"),
            Membership(organisation=org, user=admin, role="client_admin", status="active"),
            Membership(organisation=org, user=contributor, role="contributor", status="active"),
            Membership(organisation=org, user=viewer, role="viewer", status="active"),
            Membership(organisation=org, user=inactive, role="viewer", status="inactive"),
        ])
        db.commit()
        return org.id, workspace.id


def get_settings(client: TestClient, *, org_id: str, workspace_id: str, email: str, role: str = "viewer"):
    return client.get(
        f"/api/v1/workspaces/{workspace_id}/settings",
        params={"organisation_id": org_id},
        headers=headers(email, role),
    )


def patch_settings(client: TestClient, *, org_id: str, workspace_id: str, email: str, role: str = "client_admin", name: str = "Updated Workspace", language: str = "fr", expected_updated_at: str | None = None):
    body: dict[str, str] = {"name": name, "default_language": language}
    if expected_updated_at is not None:
        body["expected_updated_at"] = expected_updated_at
    return client.patch(
        f"/api/v1/workspaces/{workspace_id}/settings",
        params={"organisation_id": org_id},
        headers=headers(email, role),
        json=body,
    )


def test_settings_read_is_tenant_scoped_and_safe(client: TestClient) -> None:
    org_id, workspace_id = seed_settings_tenant(client)

    response = get_settings(client, org_id=org_id, workspace_id=workspace_id, email="viewer-alpha@example.test")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["workspace"]["id"] == workspace_id
    assert payload["organisation"]["id"] == org_id
    assert payload["membership_summary"] == {"total": 5, "active": 4, "inactive": 1, "administrators": 2}
    assert "workspace.name" in payload["capabilities"]["editable_fields"]
    rendered = str(payload).lower()
    assert "database_url" in rendered
    assert "sqlite" not in rendered
    assert "redis://" not in rendered
    assert "connection_string" in rendered
    assert "applicationinsights_connection_string" not in payload["operational"]


def test_settings_update_is_rbac_protected_and_audited(client: TestClient) -> None:
    org_id, workspace_id = seed_settings_tenant(client)

    viewer_denied = patch_settings(client, org_id=org_id, workspace_id=workspace_id, email="viewer-alpha@example.test", role="viewer")
    assert viewer_denied.status_code == 403

    current = get_settings(client, org_id=org_id, workspace_id=workspace_id, email="admin-alpha@example.test", role="client_admin").json()["data"]
    response = patch_settings(
        client,
        org_id=org_id,
        workspace_id=workspace_id,
        email="admin-alpha@example.test",
        expected_updated_at=current["workspace"]["updated_at"],
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["workspace"]["name"] == "Updated Workspace"
    assert payload["workspace"]["default_language"] == "fr"

    with client.app.state.testing_session() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == "workspace.settings.updated").all()
        assert len(events) == 1
        assert events[0].entity_id == workspace_id
        assert set(events[0].metadata_json["changed_fields"]) == {"name", "default_language"}


def test_settings_contributor_can_read_but_not_mutate(client: TestClient) -> None:
    org_id, workspace_id = seed_settings_tenant(client)

    read_response = get_settings(client, org_id=org_id, workspace_id=workspace_id, email="contributor-alpha@example.test", role="contributor")
    write_response = patch_settings(client, org_id=org_id, workspace_id=workspace_id, email="contributor-alpha@example.test", role="contributor")

    assert read_response.status_code == 200
    assert write_response.status_code == 403


def test_settings_cross_tenant_and_wrong_workspace_are_rejected(client: TestClient) -> None:
    org_a, workspace_a = seed_settings_tenant(client, slug="alpha")
    _org_b, workspace_b = seed_settings_tenant(client, slug="beta")

    cross_tenant = get_settings(client, org_id=org_a, workspace_id=workspace_a, email="admin-beta@example.test", role="client_admin")
    wrong_workspace = get_settings(client, org_id=org_a, workspace_id=workspace_b, email="admin-alpha@example.test", role="client_admin")

    assert cross_tenant.status_code == 403
    assert wrong_workspace.status_code == 404


def test_settings_update_rejects_stale_timestamp_and_invalid_payload(client: TestClient) -> None:
    org_id, workspace_id = seed_settings_tenant(client)

    stale = patch_settings(
        client,
        org_id=org_id,
        workspace_id=workspace_id,
        email="admin-alpha@example.test",
        expected_updated_at="2020-01-01T00:00:00Z",
    )
    invalid = patch_settings(client, org_id=org_id, workspace_id=workspace_id, email="admin-alpha@example.test", name="", language="e")

    assert stale.status_code == 409
    assert invalid.status_code == 422
