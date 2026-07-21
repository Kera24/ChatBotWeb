import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.models import AuditEvent, DocumentVersion, Membership, Organisation, User, Workspace
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


def upload_file(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    email: str,
    role: str,
    filename: str = "admissions.txt",
    content: bytes = b"Admissions text for extraction",
) -> tuple[str, str]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        params={"organisation_id": organisation_id},
        files={"file": (filename, content, "text/plain")},
        data={"title": "Admissions Upload"},
        headers=dev_headers(email, role),
    )
    assert response.status_code == 201
    data = response.json()["data"]
    return data["document"]["id"], data["document_version"]["id"]


def extract_url(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/extract"


def test_client_admin_can_manually_extract_uploaded_version(client: TestClient, tmp_path) -> None:
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
        document_id, version_id = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
        )

        response = client.post(
            extract_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["success"] is True
        assert body["meta"]["previous_status"] == "uploaded"
        assert body["meta"]["new_status"] == "ready"
        assert body["data"]["processing_status"] == "ready"
        assert body["data"]["processing_error"] is None
        assert body["data"]["extracted_text_path"] is not None
        extracted_path = tmp_path / body["data"]["extracted_text_path"]
        assert extracted_path.read_text(encoding="utf-8") == "Admissions text for extraction"
        with client.app.state.testing_session() as db:
            version = db.get(DocumentVersion, version_id)
            assert version is not None
            assert version.processing_status == "ready"
            assert version.extracted_text_path == body["data"]["extracted_text_path"]
            extraction_event = (
                db.query(AuditEvent)
                .filter(AuditEvent.action == "document_version.extraction.succeeded")
                .one()
            )
            assert extraction_event.actor_user_id == user_id
            assert extraction_event.previous_status == "uploaded"
            assert extraction_event.new_status == "ready"
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_parser_failure_marks_version_failed_and_audits(client: TestClient, tmp_path) -> None:
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
        document_id, version_id = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
            filename="broken.pdf",
            content=b"not actually a pdf",
        )

        response = client.post(
            extract_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["success"] is False
        assert body["meta"]["previous_status"] == "uploaded"
        assert body["meta"]["new_status"] == "failed"
        assert body["meta"]["error_code"] == "EXTRACTION_FAILED"
        assert body["data"]["processing_status"] == "failed"
        assert body["data"]["processing_error"] == "Text extraction failed for this document."
        with client.app.state.testing_session() as db:
            extraction_event = (
                db.query(AuditEvent)
                .filter(AuditEvent.action == "document_version.extraction.failed")
                .one()
            )
            assert extraction_event.document_version_id == version_id
            assert extraction_event.previous_status == "uploaded"
            assert extraction_event.new_status == "failed"
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_viewer_cannot_trigger_manual_extraction(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = client.post(
        extract_url(workspace_id, "document-id", "version-id"),
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert response.status_code == 403


def test_cross_tenant_manual_extraction_denied(client: TestClient, tmp_path) -> None:
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
        document_id, version_id = upload_file(
            client,
            organisation_id=org_a_id,
            workspace_id=workspace_a_id,
            email="alpha-admin@example.test",
            role="client_admin",
        )

        non_member_response = client.post(
            extract_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_a_id},
            headers=dev_headers("beta-admin@example.test", "client_admin"),
        )
        workspace_mismatch_response = client.post(
            extract_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_b_id},
            headers=dev_headers("beta-admin@example.test", "client_admin"),
        )

        assert non_member_response.status_code == 403
        assert workspace_mismatch_response.status_code == 404
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_manual_extraction_rejects_invalid_status(client: TestClient, tmp_path) -> None:
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
        document_id, version_id = upload_file(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            email="admin@example.test",
            role="client_admin",
        )
        with client.app.state.testing_session() as db:
            version = db.get(DocumentVersion, version_id)
            assert version is not None
            version.processing_status = "ready"
            db.add(version)
            db.commit()

        response = client.post(
            extract_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 400
        assert "processing_status 'uploaded'" in response.json()["detail"]
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
