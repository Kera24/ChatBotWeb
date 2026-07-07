import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Organisation, Workspace
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

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_can_create_and_list_organisations(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/admin/organisations",
        json={"name": "Example College", "slug": "example-college"},
    )
    list_response = client.get("/api/v1/admin/organisations")

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["success"] is True
    assert created_payload["data"]["name"] == "Example College"
    assert created_payload["data"]["slug"] == "example-college"

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert [organisation["slug"] for organisation in list_payload["data"]] == [
        "example-college"
    ]


def test_can_create_and_list_workspaces_inside_organisation(client: TestClient) -> None:
    organisation_id = client.post(
        "/api/v1/admin/organisations",
        json={"name": "Example College", "slug": "example-college"},
    ).json()["data"]["id"]

    create_response = client.post(
        f"/api/v1/orgs/{organisation_id}/workspaces",
        json={"name": "Admissions Assistant", "slug": "admissions"},
    )
    list_response = client.get(f"/api/v1/orgs/{organisation_id}/workspaces")

    assert create_response.status_code == 201
    created_payload = create_response.json()
    assert created_payload["data"]["organisation_id"] == organisation_id
    assert created_payload["data"]["slug"] == "admissions"

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert [workspace["slug"] for workspace in list_payload["data"]] == ["admissions"]


def test_workspace_detail_requires_matching_organisation_context(client: TestClient) -> None:
    org_a_id = client.post(
        "/api/v1/admin/organisations",
        json={"name": "Alpha College", "slug": "alpha"},
    ).json()["data"]["id"]
    org_b_id = client.post(
        "/api/v1/admin/organisations",
        json={"name": "Beta Clinic", "slug": "beta"},
    ).json()["data"]["id"]
    workspace_id = client.post(
        f"/api/v1/orgs/{org_a_id}/workspaces",
        json={"name": "Admissions", "slug": "admissions"},
    ).json()["data"]["id"]

    correct_scope_response = client.get(
        f"/api/v1/workspaces/{workspace_id}",
        params={"organisation_id": org_a_id},
    )
    wrong_scope_response = client.get(
        f"/api/v1/workspaces/{workspace_id}",
        params={"organisation_id": org_b_id},
    )
    missing_scope_response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert correct_scope_response.status_code == 200
    assert correct_scope_response.json()["data"]["id"] == workspace_id
    assert wrong_scope_response.status_code == 404
    assert missing_scope_response.status_code == 422


def test_workspace_list_does_not_cross_tenant_boundaries(client: TestClient) -> None:
    org_a_id = client.post(
        "/api/v1/admin/organisations",
        json={"name": "Alpha College", "slug": "alpha"},
    ).json()["data"]["id"]
    org_b_id = client.post(
        "/api/v1/admin/organisations",
        json={"name": "Beta Clinic", "slug": "beta"},
    ).json()["data"]["id"]
    client.post(f"/api/v1/orgs/{org_a_id}/workspaces", json={"name": "A", "slug": "a"})
    client.post(f"/api/v1/orgs/{org_b_id}/workspaces", json={"name": "B", "slug": "b"})

    response = client.get(f"/api/v1/orgs/{org_a_id}/workspaces")

    assert response.status_code == 200
    workspaces = response.json()["data"]
    assert len(workspaces) == 1
    assert workspaces[0]["organisation_id"] == org_a_id


def test_workspace_creation_requires_existing_organisation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/orgs/missing-organisation/workspaces",
        json={"name": "Admissions", "slug": "admissions"},
    )

    assert response.status_code == 404
