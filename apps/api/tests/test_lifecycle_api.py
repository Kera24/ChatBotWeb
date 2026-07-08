import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Document, DocumentVersion, Membership, Organisation, User, Workspace
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


def seed_document_version(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    document_status: str = "uploaded",
    version_status: str = "pending",
) -> tuple[str, str]:
    with client.app.state.testing_session() as db:
        document = Document(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title="Admissions Handbook",
            source_type="pdf",
            source_key=f"admissions-{uuid4()}.pdf",
            status=document_status,
        )
        version = DocumentVersion(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document=document,
            version_number=1,
            checksum=f"sha256:{uuid4()}",
            processing_status=version_status,
        )
        db.add_all([document, version])
        db.commit()
        return document.id, version.id


def document_transition_url(workspace_id: str, document_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/transition"


def version_transition_url(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/transition"


def test_client_admin_can_transition_own_workspace_document(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="admin@example.test",
        role="client_admin",
    )
    document_id, _version_id = seed_document_version(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )

    response = client.post(
        document_transition_url(workspace_id, document_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "processing"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "processing"
    assert body["meta"] == {"previous_status": "uploaded", "new_status": "processing"}


def test_client_admin_can_transition_own_workspace_document_version(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="admin@example.test",
        role="client_admin",
    )
    document_id, version_id = seed_document_version(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        version_status="pending",
    )

    response = client.post(
        version_transition_url(workspace_id, document_id, version_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "queued"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert response.status_code == 200
    assert response.json()["data"]["processing_status"] == "queued"
    assert response.json()["meta"] == {"previous_status": "pending", "new_status": "queued"}


def test_viewer_cannot_transition_document_or_version(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    document_id, version_id = seed_document_version(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )

    document_response = client.post(
        document_transition_url(workspace_id, document_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "processing"},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    version_response = client.post(
        version_transition_url(workspace_id, document_id, version_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "queued"},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert document_response.status_code == 403
    assert version_response.status_code == 403


def test_invalid_transition_returns_clear_error(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="admin@example.test",
        role="client_admin",
    )
    document_id, version_id = seed_document_version(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )

    document_response = client.post(
        document_transition_url(workspace_id, document_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "ready"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )
    version_response = client.post(
        version_transition_url(workspace_id, document_id, version_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "ready"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert document_response.status_code == 400
    assert "Invalid lifecycle transition" in document_response.json()["detail"]
    assert version_response.status_code == 400
    assert "Invalid lifecycle transition" in version_response.json()["detail"]


def test_cross_tenant_transition_fails(client: TestClient) -> None:
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
    document_id, version_id = seed_document_version(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
    )

    document_response = client.post(
        document_transition_url(workspace_b_id, document_id),
        params={"organisation_id": org_b_id},
        json={"target_status": "processing"},
        headers=dev_headers("beta-admin@example.test", "client_admin"),
    )
    version_response = client.post(
        version_transition_url(workspace_b_id, document_id, version_id),
        params={"organisation_id": org_b_id},
        json={"target_status": "queued"},
        headers=dev_headers("beta-admin@example.test", "client_admin"),
    )

    assert document_response.status_code == 404
    assert version_response.status_code == 404


def test_archived_and_expired_terminal_behaviour_preserved(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="admin@example.test",
        role="client_admin",
    )
    archived_document_id, _archived_version_id = seed_document_version(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_status="ready",
        version_status="ready",
    )
    expired_document_id, _expired_version_id = seed_document_version(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_status="ready",
        version_status="ready",
    )

    archive_response = client.post(
        document_transition_url(workspace_id, archived_document_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "archived"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )
    expire_response = client.post(
        document_transition_url(workspace_id, expired_document_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "expired"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )
    archived_retry = client.post(
        document_transition_url(workspace_id, archived_document_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "ready"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )
    expired_retry = client.post(
        document_transition_url(workspace_id, expired_document_id),
        params={"organisation_id": organisation_id},
        json={"target_status": "ready"},
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert archive_response.status_code == 200
    assert archive_response.json()["data"]["archived_at"] is not None
    assert expire_response.status_code == 200
    assert expire_response.json()["data"]["expires_at"] is not None
    assert archived_retry.status_code == 400
    assert expired_retry.status_code == 400
