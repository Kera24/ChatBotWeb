import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.config import settings
from app.db.models import AuditEvent, Document, DocumentVersion, Membership, Organisation, User, Workspace
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


def seed_document(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    title: str = "Admissions Handbook",
) -> str:
    with client.app.state.testing_session() as db:
        document = Document(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=title,
            source_type="pdf",
            source_key=f"{title.lower().replace(' ', '-')}.pdf",
        )
        db.add(document)
        db.commit()
        return document.id


def test_client_admin_can_create_metadata_only_document(client: TestClient) -> None:
    organisation_id, workspace_id, user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="admin@example.test",
        role="client_admin",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        params={"organisation_id": organisation_id},
        json={
            "title": "Admissions Handbook",
            "source_type": "pdf",
            "source_key": "admissions-handbook.pdf",
            "category": "admissions",
            "visibility": "workspace",
            "metadata_json": {"language": "en", "tags": ["admissions"]},
        },
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["organisation_id"] == organisation_id
    assert data["workspace_id"] == workspace_id
    assert data["title"] == "Admissions Handbook"
    assert data["status"] == "uploaded"
    assert data["created_by_user_id"] == user_id


def test_viewer_can_list_and_read_documents(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    document_id = seed_document(client, organisation_id=organisation_id, workspace_id=workspace_id)

    list_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/documents",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    read_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["data"]] == [document_id]
    assert read_response.status_code == 200
    assert read_response.json()["data"]["id"] == document_id


def test_viewer_cannot_create_document(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        params={"organisation_id": organisation_id},
        json={"title": "Admissions Handbook", "source_type": "pdf"},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert response.status_code == 403


def test_document_read_does_not_cross_tenant_boundaries(client: TestClient) -> None:
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
    document_id = seed_document(client, organisation_id=org_a_id, workspace_id=workspace_a_id)

    wrong_member_response = client.get(
        f"/api/v1/workspaces/{workspace_a_id}/documents/{document_id}",
        params={"organisation_id": org_a_id},
        headers=dev_headers("beta-admin@example.test", "client_admin"),
    )
    wrong_workspace_response = client.get(
        f"/api/v1/workspaces/{workspace_b_id}/documents/{document_id}",
        params={"organisation_id": org_b_id},
        headers=dev_headers("beta-admin@example.test", "client_admin"),
    )

    assert wrong_member_response.status_code == 403
    assert wrong_workspace_response.status_code == 404


def test_document_list_requires_workspace_to_belong_to_organisation(client: TestClient) -> None:
    org_a_id, workspace_a_id, _user_a_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-admin@example.test",
        role="client_admin",
    )
    org_b_id, _workspace_b_id, _user_b_id = seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-admin@example.test",
        role="client_admin",
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace_a_id}/documents",
        params={"organisation_id": org_b_id},
        headers=dev_headers("beta-admin@example.test", "client_admin"),
    )

    assert response.status_code == 404

def upload_file(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    email: str,
    role: str,
    filename: str = "admissions.txt",
    content: bytes = b"Admissions content",
) -> object:
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        params={"organisation_id": organisation_id},
        files={"file": (filename, content, "text/plain")},
        data={"title": "Admissions Upload", "category": "admissions"},
        headers=dev_headers(email, role),
    )


def test_client_admin_can_upload_supported_file(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    try:
        organisation_id, workspace_id, user_id = seed_tenant(
            client,
            organisation_name="Alpha College",
            organisation_slug="alpha",
            user_email="admin@example.test",
            role="client_admin",
        )

        response = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
        )

        assert response.status_code == 201
        data = response.json()["data"]
        document = data["document"]
        version = data["document_version"]
        assert document["organisation_id"] == organisation_id
        assert document["workspace_id"] == workspace_id
        assert document["title"] == "Admissions Upload"
        assert document["source_type"] == "txt"
        assert document["status"] == "uploaded"
        assert document["created_by_user_id"] == user_id
        assert document["active_document_version_id"] == version["id"]
        assert version["document_id"] == document["id"]
        assert version["processing_status"] == "uploaded"
        assert (tmp_path / version["original_file_path"]).exists()
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_viewer_cannot_upload_file(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    try:
        organisation_id, workspace_id, _user_id = seed_tenant(
            client,
            organisation_name="Alpha College",
            organisation_slug="alpha",
            user_email="viewer@example.test",
            role="viewer",
        )

        response = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="viewer@example.test",
            role="viewer",
        )

        assert response.status_code == 403
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_unsupported_file_type_rejected(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    try:
        organisation_id, workspace_id, _user_id = seed_tenant(
            client,
            organisation_name="Alpha College",
            organisation_slug="alpha",
            user_email="admin@example.test",
            role="client_admin",
        )

        response = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
            filename="malware.exe",
        )

        assert response.status_code == 415
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_oversized_file_rejected_when_max_size_exists(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    original_max = settings.MAX_UPLOAD_BYTES
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    object.__setattr__(settings, "MAX_UPLOAD_BYTES", 4)
    try:
        organisation_id, workspace_id, _user_id = seed_tenant(
            client,
            organisation_name="Alpha College",
            organisation_slug="alpha",
            user_email="admin@example.test",
            role="client_admin",
        )

        response = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
            content=b"too large",
        )

        assert response.status_code == 413
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
        object.__setattr__(settings, "MAX_UPLOAD_BYTES", original_max)


def test_cross_tenant_upload_denied(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    try:
        org_a_id, workspace_a_id, _user_a_id = seed_tenant(
            client,
            organisation_name="Alpha College",
            organisation_slug="alpha",
            user_email="alpha-admin@example.test",
            role="client_admin",
        )
        org_b_id, _workspace_b_id, _user_b_id = seed_tenant(
            client,
            organisation_name="Beta Clinic",
            organisation_slug="beta",
            user_email="beta-admin@example.test",
            role="client_admin",
        )

        response = upload_file(
            client,
            organisation_id=org_a_id,
            workspace_id=workspace_a_id,
            email="beta-admin@example.test",
            role="client_admin",
        )
        workspace_mismatch_response = upload_file(
            client,
            organisation_id=org_b_id,
            workspace_id=workspace_a_id,
            email="beta-admin@example.test",
            role="client_admin",
        )

        assert response.status_code == 403
        assert workspace_mismatch_response.status_code == 404
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_upload_creates_document_and_document_version(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    try:
        organisation_id, workspace_id, _user_id = seed_tenant(
            client,
            organisation_name="Alpha College",
            organisation_slug="alpha",
            user_email="admin@example.test",
            role="client_admin",
        )

        response = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
            filename="policy.pdf",
            content=b"%PDF-1.4",
        )

        assert response.status_code == 201
        document_id = response.json()["data"]["document"]["id"]
        version_id = response.json()["data"]["document_version"]["id"]
        with client.app.state.testing_session() as db:
            document = db.get(Document, document_id)
            version = db.get(DocumentVersion, version_id)
            assert document is not None
            assert version is not None
            assert document.status == "uploaded"
            assert version.processing_status == "uploaded"
            assert document.active_document_version_id == version.id
            assert version.original_file_path is not None
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_upload_creates_audit_event(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    try:
        organisation_id, workspace_id, user_id = seed_tenant(
            client,
            organisation_name="Alpha College",
            organisation_slug="alpha",
            user_email="admin@example.test",
            role="client_admin",
        )

        response = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
        )

        assert response.status_code == 201
        document_id = response.json()["data"]["document"]["id"]
        version_id = response.json()["data"]["document_version"]["id"]
        with client.app.state.testing_session() as db:
            events = db.query(AuditEvent).all()
            assert len(events) == 1
            event = events[0]
            assert event.organisation_id == organisation_id
            assert event.workspace_id == workspace_id
            assert event.actor_user_id == user_id
            assert event.action == "document.uploaded"
            assert event.entity_type == "document"
            assert event.entity_id == document_id
            assert event.document_id == document_id
            assert event.document_version_id == version_id
            assert event.new_status == "uploaded"
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
