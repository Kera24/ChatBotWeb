import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.models import AuditEvent, Chunk, DocumentVersion, Membership, Organisation, User, Workspace
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
) -> tuple[str, str]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        params={"organisation_id": organisation_id},
        files={"file": ("sample.txt", b"one two three four five six seven eight", "text/plain")},
        data={"title": "Embedding Sample"},
        headers=dev_headers(email, role),
    )
    assert response.status_code == 201
    data = response.json()["data"]
    return data["document"]["id"], data["document_version"]["id"]


def prepare_chunked_version(client: TestClient, tmp_path, *, email: str = "admin@example.test") -> tuple[str, str, str, str]:
    object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email=email,
        role="client_admin",
    )
    document_id, version_id = upload_file(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email=email,
        role="client_admin",
    )
    extract_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/extract",
        params={"organisation_id": organisation_id},
        headers=dev_headers(email, "client_admin"),
    )
    assert extract_response.status_code == 200
    chunk_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunk",
        params={"organisation_id": organisation_id},
        headers=dev_headers(email, "client_admin"),
    )
    assert chunk_response.status_code == 200
    return organisation_id, workspace_id, document_id, version_id


def embed_url(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/embed"


def test_client_admin_can_embed_ready_chunks(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "local-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    try:
        organisation_id, workspace_id, document_id, version_id = prepare_chunked_version(client, tmp_path)

        response = client.post(
            embed_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        assert response.json()["meta"]["success"] is True
        assert response.json()["meta"]["embedded_chunk_count"] == 1
        with client.app.state.testing_session() as db:
            chunk = db.query(Chunk).one()
            assert chunk.embedding_provider == "local-mock"
            assert chunk.embedding_model == "local-test"
            assert chunk.embedding_dimension == 8
            assert chunk.embedding_created_at is not None
            assert chunk.embedding_vector is None
            assert chunk.metadata_json["embedding"]["vector_stored"] is False
            event = (
                db.query(AuditEvent)
                .filter(AuditEvent.action == "document_version.embedding.succeeded")
                .one()
            )
            assert event.document_version_id == version_id
            assert event.metadata_json["embedded_chunk_count"] == 1
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
        object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
        object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
        object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)


def test_viewer_cannot_trigger_embedding(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = client.post(
        embed_url(workspace_id, "document-id", "version-id"),
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert response.status_code == 403


def test_cross_tenant_embedding_denied(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    try:
        org_a_id, workspace_a_id, document_id, version_id = prepare_chunked_version(
            client,
            tmp_path,
            email="alpha-admin@example.test",
        )
        org_b_id, _workspace_b_id, _user_b_id = seed_tenant(
            client,
            organisation_name="Beta Clinic",
            organisation_slug="beta",
            user_email="beta-admin@example.test",
            role="client_admin",
        )

        non_member_response = client.post(
            embed_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_a_id},
            headers=dev_headers("beta-admin@example.test", "client_admin"),
        )
        workspace_mismatch_response = client.post(
            embed_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_b_id},
            headers=dev_headers("beta-admin@example.test", "client_admin"),
        )

        assert non_member_response.status_code == 403
        assert workspace_mismatch_response.status_code == 404
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_embedding_rejects_invalid_version_or_chunk_state(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    try:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", str(tmp_path))
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

        invalid_version_response = client.post(
            embed_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )
        assert invalid_version_response.status_code == 400
        assert "processing_status 'ready'" in invalid_version_response.json()["detail"]

        with client.app.state.testing_session() as db:
            version = db.get(DocumentVersion, version_id)
            assert version is not None
            version.processing_status = "ready"
            db.add(version)
            db.commit()
        no_chunks_response = client.post(
            embed_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )
        assert no_chunks_response.status_code == 400
        assert "at least one ready chunk" in no_chunks_response.json()["detail"]
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_provider_failure_is_handled_safely(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "failing-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "failing-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    try:
        organisation_id, workspace_id, document_id, version_id = prepare_chunked_version(client, tmp_path)

        response = client.post(
            embed_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        assert response.json()["meta"]["success"] is False
        assert response.json()["meta"]["error_code"] == "EMBEDDING_PROVIDER_FAILED"
        with client.app.state.testing_session() as db:
            chunk = db.query(Chunk).one()
            assert chunk.embedding_provider is None
            event = (
                db.query(AuditEvent)
                .filter(AuditEvent.action == "document_version.embedding.failed")
                .one()
            )
            assert event.document_version_id == version_id
            assert event.metadata_json["error_code"] == "EMBEDDING_PROVIDER_FAILED"
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
        object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
        object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
        object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)
