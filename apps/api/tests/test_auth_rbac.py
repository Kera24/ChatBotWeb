import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
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


def seed_member(
    client: TestClient,
    *,
    organisation_name: str = "Example College",
    organisation_slug: str = "example-college",
    user_email: str = "admin@example.test",
    role: str = "client_admin",
) -> tuple[str, str]:
    with client.app.state.testing_session() as db:
        organisation = Organisation(name=organisation_name, slug=organisation_slug)
        user = User(email=user_email)
        workspace = Workspace(
            organisation=organisation,
            name="Admissions Assistant",
            slug="admissions",
        )
        membership = Membership(organisation=organisation, user=user, role=role)
        db.add_all([organisation, user, workspace, membership])
        db.commit()
        return organisation.id, user.id


def test_super_admin_can_access_admin_organisation_list(client: TestClient) -> None:
    response = client.get(
        "/api/v1/admin/organisations",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200


def test_non_super_admin_cannot_access_admin_organisation_list(client: TestClient) -> None:
    seed_member(client, user_email="client-admin@example.test", role="client_admin")

    response = client.get(
        "/api/v1/admin/organisations",
        headers=dev_headers("client-admin@example.test", "client_admin"),
    )

    assert response.status_code == 403


def test_org_member_can_access_own_organisation_workspaces(client: TestClient) -> None:
    organisation_id, _user_id = seed_member(
        client,
        user_email="owner@example.test",
        role="org_owner",
    )

    response = client.get(
        f"/api/v1/orgs/{organisation_id}/workspaces",
        headers=dev_headers("owner@example.test", "org_owner"),
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["organisation_id"] == organisation_id


def test_non_member_cannot_access_another_organisation_workspaces(
    client: TestClient,
) -> None:
    organisation_id, _user_id = seed_member(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-owner@example.test",
        role="org_owner",
    )
    seed_member(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-owner@example.test",
        role="org_owner",
    )

    response = client.get(
        f"/api/v1/orgs/{organisation_id}/workspaces",
        headers=dev_headers("beta-owner@example.test", "org_owner"),
    )

    assert response.status_code == 403
