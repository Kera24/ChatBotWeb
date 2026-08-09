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
    content: bytes = b"one two three four five six seven eight nine ten eleven twelve",
) -> tuple[str, str]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        params={"organisation_id": organisation_id},
        files={"file": ("sample.txt", content, "text/plain")},
        data={"title": "Chunk Sample"},
        headers=dev_headers(email, role),
    )
    assert response.status_code == 201
    data = response.json()["data"]
    return data["document"]["id"], data["document_version"]["id"]


def extract_version(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    version_id: str,
    email: str,
    role: str,
) -> None:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/extract",
        params={"organisation_id": organisation_id},
        headers=dev_headers(email, role),
    )
    assert response.status_code == 200
    assert response.json()["meta"]["success"] is True


def prepare_ready_version(client: TestClient, tmp_path, *, email: str = "admin@example.test") -> tuple[str, str, str]:
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
    extract_version(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        version_id=version_id,
        email=email,
        role="client_admin",
    )
    return organisation_id, workspace_id, document_id, version_id


def chunk_url(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunk"


def test_client_admin_can_create_chunks(client: TestClient, tmp_path) -> None:
    # Explicitly pins the fixed_word baseline algorithm regardless of
    # settings.CHUNKING_STRATEGY's ambient default (structure_aware as of
    # the Knowledge Pipeline V2 chunking-corpus bake-off promotion - see
    # docs/engineering/chunking.md) - this test's intent is to verify the
    # baseline's exact word-boundary/overlap behavior, not "whatever the
    # current default happens to be".
    original_root = settings.LOCAL_UPLOAD_ROOT
    original_size = settings.CHUNK_SIZE_WORDS
    original_overlap = settings.CHUNK_OVERLAP_WORDS
    original_strategy = settings.CHUNKING_STRATEGY
    object.__setattr__(settings, "CHUNK_SIZE_WORDS", 5)
    object.__setattr__(settings, "CHUNK_OVERLAP_WORDS", 1)
    object.__setattr__(settings, "CHUNKING_STRATEGY", "fixed_word")
    try:
        organisation_id, workspace_id, document_id, version_id = prepare_ready_version(client, tmp_path)

        response = client.post(
            chunk_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        assert response.json()["meta"]["success"] is True
        assert response.json()["meta"]["chunk_count"] == 3
        with client.app.state.testing_session() as db:
            chunks = db.query(Chunk).order_by(Chunk.chunk_index).all()
            assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
            assert chunks[0].content == "one two three four five"
            assert chunks[1].content == "five six seven eight nine"
            assert chunks[2].content == "nine ten eleven twelve"
            assert all(chunk.status == "ready" for chunk in chunks)
            assert all(chunk.source_title == "Chunk Sample" for chunk in chunks)
            assert all(chunk.source_type == "txt" for chunk in chunks)
            assert all(chunk.chunking_strategy_version == "mvp-word-v1" for chunk in chunks)
            event = (
                db.query(AuditEvent)
                .filter(AuditEvent.action == "document_version.chunking.succeeded")
                .one()
            )
            assert event.document_version_id == version_id
            assert event.metadata_json["chunk_count"] == 3
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
        object.__setattr__(settings, "CHUNK_SIZE_WORDS", original_size)
        object.__setattr__(settings, "CHUNK_OVERLAP_WORDS", original_overlap)
        object.__setattr__(settings, "CHUNKING_STRATEGY", original_strategy)


def test_viewer_cannot_trigger_chunking(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = client.post(
        chunk_url(workspace_id, "document-id", "version-id"),
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert response.status_code == 403


def test_cross_tenant_chunking_denied(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    try:
        org_a_id, workspace_a_id, document_id, version_id = prepare_ready_version(
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
            chunk_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_a_id},
            headers=dev_headers("beta-admin@example.test", "client_admin"),
        )
        workspace_mismatch_response = client.post(
            chunk_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_b_id},
            headers=dev_headers("beta-admin@example.test", "client_admin"),
        )

        assert non_member_response.status_code == 403
        assert workspace_mismatch_response.status_code == 404
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_chunking_rejects_invalid_version_status(client: TestClient, tmp_path) -> None:
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

        response = client.post(
            chunk_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 400
        assert "processing_status 'ready'" in response.json()["detail"]
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_chunking_fails_without_extracted_text_path(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    try:
        organisation_id, workspace_id, document_id, version_id = prepare_ready_version(client, tmp_path)
        with client.app.state.testing_session() as db:
            version = db.get(DocumentVersion, version_id)
            assert version is not None
            version.extracted_text_path = None
            db.add(version)
            db.commit()

        response = client.post(
            chunk_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        assert response.json()["meta"]["success"] is False
        assert response.json()["meta"]["error_code"] == "EXTRACTED_TEXT_MISSING"
        with client.app.state.testing_session() as db:
            event = (
                db.query(AuditEvent)
                .filter(AuditEvent.action == "document_version.chunking.failed")
                .one()
            )
            assert event.metadata_json["error_code"] == "EXTRACTED_TEXT_MISSING"
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)


def test_structure_aware_strategy_endpoint_persists_metadata_and_respects_tenant_isolation(client: TestClient, tmp_path) -> None:
    # Knowledge Pipeline V2 Phase 9: the strategy-selection wiring in
    # chunk_document_version_endpoint (settings.CHUNKING_STRATEGY) must
    # still go through the same ensure_workspace_in_organisation/tenant
    # filters as the fixed_word baseline - selecting a candidate strategy
    # must never become a second, unchecked code path.
    original_root = settings.LOCAL_UPLOAD_ROOT
    original_strategy = settings.CHUNKING_STRATEGY
    object.__setattr__(settings, "CHUNKING_STRATEGY", "structure_aware")
    try:
        org_a_id, workspace_a_id, document_id, version_id = prepare_ready_version(
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

        cross_tenant_response = client.post(
            chunk_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_b_id},
            headers=dev_headers("beta-admin@example.test", "client_admin"),
        )
        assert cross_tenant_response.status_code == 404

        response = client.post(
            chunk_url(workspace_a_id, document_id, version_id),
            params={"organisation_id": org_a_id},
            headers=dev_headers("alpha-admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        assert response.json()["meta"]["success"] is True
        with client.app.state.testing_session() as db:
            chunks = db.query(Chunk).order_by(Chunk.chunk_index).all()
            assert len(chunks) >= 1
            assert all(chunk.organisation_id == org_a_id for chunk in chunks)
            assert all(chunk.workspace_id == workspace_a_id for chunk in chunks)
            assert all(chunk.chunking_strategy_version == "structure_aware:structure-aware-v1" for chunk in chunks)
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
        object.__setattr__(settings, "CHUNKING_STRATEGY", original_strategy)


def test_chunking_strategy_rollback_to_fixed_word(client: TestClient, tmp_path) -> None:
    # Phase 8/9: rollback to the production baseline must be a pure config
    # flip - no code change, no data migration - and must reproduce the
    # exact original chunk_document_version() code path (strategy=None).
    original_root = settings.LOCAL_UPLOAD_ROOT
    original_strategy = settings.CHUNKING_STRATEGY
    original_size = settings.CHUNK_SIZE_WORDS
    original_overlap = settings.CHUNK_OVERLAP_WORDS
    object.__setattr__(settings, "CHUNKING_STRATEGY", "structure_aware")
    object.__setattr__(settings, "CHUNK_SIZE_WORDS", 5)
    object.__setattr__(settings, "CHUNK_OVERLAP_WORDS", 1)
    try:
        organisation_id, workspace_id, document_id, version_id = prepare_ready_version(client, tmp_path)

        object.__setattr__(settings, "CHUNKING_STRATEGY", "fixed_word")
        response = client.post(
            chunk_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert response.status_code == 200
        assert response.json()["meta"]["chunk_count"] == 3
        with client.app.state.testing_session() as db:
            chunks = db.query(Chunk).order_by(Chunk.chunk_index).all()
            assert [chunk.content for chunk in chunks] == [
                "one two three four five",
                "five six seven eight nine",
                "nine ten eleven twelve",
            ]
            assert all(chunk.chunking_strategy_version == "mvp-word-v1" for chunk in chunks)
            assert all(chunk.heading_path is None for chunk in chunks)
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
        object.__setattr__(settings, "CHUNKING_STRATEGY", original_strategy)
        object.__setattr__(settings, "CHUNK_SIZE_WORDS", original_size)
        object.__setattr__(settings, "CHUNK_OVERLAP_WORDS", original_overlap)


def test_repeated_chunking_is_safely_rejected(client: TestClient, tmp_path) -> None:
    original_root = settings.LOCAL_UPLOAD_ROOT
    original_size = settings.CHUNK_SIZE_WORDS
    original_overlap = settings.CHUNK_OVERLAP_WORDS
    object.__setattr__(settings, "CHUNK_SIZE_WORDS", 5)
    object.__setattr__(settings, "CHUNK_OVERLAP_WORDS", 1)
    try:
        organisation_id, workspace_id, document_id, version_id = prepare_ready_version(client, tmp_path)
        first_response = client.post(
            chunk_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )
        second_response = client.post(
            chunk_url(workspace_id, document_id, version_id),
            params={"organisation_id": organisation_id},
            headers=dev_headers("admin@example.test", "client_admin"),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 400
        assert "Chunks already exist" in second_response.json()["detail"]
    finally:
        object.__setattr__(settings, "LOCAL_UPLOAD_ROOT", original_root)
        object.__setattr__(settings, "CHUNK_SIZE_WORDS", original_size)
        object.__setattr__(settings, "CHUNK_OVERLAP_WORDS", original_overlap)
