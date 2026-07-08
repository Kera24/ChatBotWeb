import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
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


def seed_chunk(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    title: str = "Admissions Handbook",
) -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        document = Document(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=title,
            source_type="pdf",
            source_key=f"{title.lower().replace(' ', '-')}.pdf",
        )
        version = DocumentVersion(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document=document,
            version_number=1,
            checksum=f"sha256:{title.lower().replace(' ', '-')}",
            processing_status="ready",
        )
        chunk = Chunk(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document=document,
            document_version=version,
            chunk_index=0,
            content="Applications close in December.",
            content_hash="sha256:chunk-1",
            token_count=5,
            source_type="pdf",
            source_title=title,
            language="en",
            chunking_strategy_version="placeholder-v1",
            page_number=1,
            status="ready",
            metadata_json={"page_number": 1},
        )
        db.add_all([document, version, chunk])
        db.commit()
        return document.id, version.id, chunk.id


def chunk_list_url(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks"


def chunk_read_url(workspace_id: str, document_id: str, version_id: str, chunk_id: str) -> str:
    return f"{chunk_list_url(workspace_id, document_id, version_id)}/{chunk_id}"


def test_member_can_list_and_read_chunks_in_own_workspace(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    document_id, version_id, chunk_id = seed_chunk(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )

    list_response = client.get(
        chunk_list_url(workspace_id, document_id, version_id),
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    read_response = client.get(
        chunk_read_url(workspace_id, document_id, version_id, chunk_id),
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["data"]] == [chunk_id]
    assert read_response.status_code == 200
    data = read_response.json()["data"]
    assert data["id"] == chunk_id
    assert data["content"] == "Applications close in December."
    assert data["document_id"] == document_id
    assert data["document_version_id"] == version_id


def test_non_member_cannot_access_chunks(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-owner@example.test",
        role="org_owner",
    )
    seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-viewer@example.test",
        role="viewer",
    )
    document_id, version_id, chunk_id = seed_chunk(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )

    list_response = client.get(
        chunk_list_url(workspace_id, document_id, version_id),
        params={"organisation_id": organisation_id},
        headers=dev_headers("beta-viewer@example.test", "viewer"),
    )
    read_response = client.get(
        chunk_read_url(workspace_id, document_id, version_id, chunk_id),
        params={"organisation_id": organisation_id},
        headers=dev_headers("beta-viewer@example.test", "viewer"),
    )

    assert list_response.status_code == 403
    assert read_response.status_code == 403


def test_cross_tenant_chunk_access_fails(client: TestClient) -> None:
    org_a_id, workspace_a_id, _user_a_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-viewer@example.test",
        role="viewer",
    )
    org_b_id, workspace_b_id, _user_b_id = seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-viewer@example.test",
        role="viewer",
    )
    document_id, version_id, chunk_id = seed_chunk(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
    )

    response = client.get(
        chunk_read_url(workspace_b_id, document_id, version_id, chunk_id),
        params={"organisation_id": org_b_id},
        headers=dev_headers("beta-viewer@example.test", "viewer"),
    )

    assert response.status_code == 404


def test_document_version_must_belong_to_requested_organisation_workspace(client: TestClient) -> None:
    org_a_id, workspace_a_id, _user_a_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-viewer@example.test",
        role="viewer",
    )
    org_b_id, workspace_b_id, _user_b_id = seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-viewer@example.test",
        role="viewer",
    )
    document_id, version_id, _chunk_id = seed_chunk(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
    )

    organisation_mismatch = client.get(
        chunk_list_url(workspace_a_id, document_id, version_id),
        params={"organisation_id": org_b_id},
        headers=dev_headers("beta-viewer@example.test", "viewer"),
    )
    workspace_mismatch = client.get(
        chunk_list_url(workspace_b_id, document_id, version_id),
        params={"organisation_id": org_b_id},
        headers=dev_headers("beta-viewer@example.test", "viewer"),
    )

    assert organisation_mismatch.status_code == 404
    assert workspace_mismatch.status_code == 404
