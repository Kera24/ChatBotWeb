import pytest
from fastapi.testclient import TestClient
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
        workspace = Workspace(
            organisation=organisation,
            name="Knowledge Base",
            slug=f"{organisation_slug}-knowledge",
        )
        membership = Membership(organisation=organisation, user=user, role=role)
        db.add_all([organisation, user, workspace, membership])
        db.commit()
        return organisation.id, workspace.id, user.id


def add_audit_event(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    action: str = "document.status.transitioned",
) -> str:
    with client.app.state.testing_session() as db:
        event = AuditEvent(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            action=action,
            entity_type="document",
            entity_id=f"entity-{action}",
            document_id=None,
            previous_status="uploaded",
            new_status="processing",
            metadata_json={"status_field": "status"},
        )
        db.add(event)
        db.commit()
        return event.id


def test_org_owner_can_list_own_organisation_audit_events(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="owner@example.test",
        role="org_owner",
    )
    event_id = add_audit_event(client, organisation_id=organisation_id, workspace_id=workspace_id)

    response = client.get(
        f"/api/v1/orgs/{organisation_id}/audit-events",
        headers=dev_headers("owner@example.test", "org_owner"),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [event_id]


def test_client_admin_can_list_own_workspace_audit_events(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="admin@example.test",
        role="client_admin",
    )
    event_id = add_audit_event(client, organisation_id=organisation_id, workspace_id=workspace_id)

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit-events",
        params={"organisation_id": organisation_id},
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [event_id]


def test_non_member_cannot_list_audit_events(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-admin@example.test",
        role="client_admin",
    )
    seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-admin@example.test",
        role="client_admin",
    )
    add_audit_event(client, organisation_id=organisation_id, workspace_id=workspace_id)

    org_response = client.get(
        f"/api/v1/orgs/{organisation_id}/audit-events",
        headers=dev_headers("beta-admin@example.test", "client_admin"),
    )
    workspace_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit-events",
        params={"organisation_id": organisation_id},
        headers=dev_headers("beta-admin@example.test", "client_admin"),
    )

    assert org_response.status_code == 403
    assert workspace_response.status_code == 403


def test_cross_tenant_audit_events_are_never_returned(client: TestClient) -> None:
    org_a_id, workspace_a_id, _user_a_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-admin@example.test",
        role="client_admin",
    )
    org_b_id, workspace_b_id, _user_b_id = seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-admin@example.test",
        role="client_admin",
    )
    event_a_id = add_audit_event(client, organisation_id=org_a_id, workspace_id=workspace_a_id)
    event_b_id = add_audit_event(client, organisation_id=org_b_id, workspace_id=workspace_b_id)

    org_response = client.get(
        f"/api/v1/orgs/{org_a_id}/audit-events",
        headers=dev_headers("alpha-admin@example.test", "client_admin"),
    )
    workspace_response = client.get(
        f"/api/v1/workspaces/{workspace_a_id}/audit-events",
        params={"organisation_id": org_a_id},
        headers=dev_headers("alpha-admin@example.test", "client_admin"),
    )

    assert [item["id"] for item in org_response.json()["data"]] == [event_a_id]
    assert [item["id"] for item in workspace_response.json()["data"]] == [event_a_id]
    assert event_b_id not in [item["id"] for item in org_response.json()["data"]]
    assert event_b_id not in [item["id"] for item in workspace_response.json()["data"]]


def test_viewer_cannot_list_audit_events(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    add_audit_event(client, organisation_id=organisation_id, workspace_id=workspace_id)

    org_response = client.get(
        f"/api/v1/orgs/{organisation_id}/audit-events",
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    workspace_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit-events",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert org_response.status_code == 403
    assert workspace_response.status_code == 403


def test_audit_event_limit_parameter_works(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="admin@example.test",
        role="client_admin",
    )
    first_event_id = add_audit_event(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        action="document.first",
    )
    second_event_id = add_audit_event(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        action="document.second",
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit-events",
        params={"organisation_id": organisation_id, "limit": 1},
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["meta"]["limit"] == 1
    assert response.json()["data"][0]["id"] in {first_event_id, second_event_id}
