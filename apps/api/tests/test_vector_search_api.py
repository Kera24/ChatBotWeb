from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
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

    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "search-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)
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


def add_embedded_chunk(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    content: str,
    title: str,
    chunk_index: int = 0,
    embedded: bool = True,
) -> str:
    with client.app.state.testing_session() as db:
        document = Document(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=title,
            source_type="txt",
            source_key=f"{title}-{chunk_index}.txt",
            status="ready",
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            version_number=1,
            checksum=f"checksum-{title}-{chunk_index}",
            processing_status="ready",
        )
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id
        chunk = Chunk(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_index=chunk_index,
            content=content,
            content_hash=f"hash-{title}-{chunk_index}",
            token_count=len(content.split()),
            source_type="txt",
            source_title=title,
            section_title="Admissions",
            heading_path="Handbook > Admissions",
            status="ready",
            embedding_provider="local-mock" if embedded else None,
            embedding_model="search-test" if embedded else None,
            embedding_dimension=8 if embedded else None,
            embedding_created_at=datetime.now(timezone.utc) if embedded else None,
            metadata_json={"citation_label": title},
        )
        db.add(chunk)
        db.commit()
        return chunk.id


def search(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    email: str,
    role: str,
    query: str,
    limit: int = 5,
):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/search",
        params={"organisation_id": organisation_id},
        json={"query": query, "limit": limit},
        headers=dev_headers(email, role),
    )


def test_successful_tenant_scoped_search_returns_citation_metadata(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    matching_chunk_id = add_embedded_chunk(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        content="applications close in december",
        title="Admissions Handbook",
    )
    add_embedded_chunk(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        content="campus parking information",
        title="Campus Guide",
    )

    response = search(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="applications close in december",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["chunk_id"] == matching_chunk_id
    assert data[0]["score"] == pytest.approx(1.0)
    assert data[0]["source_title"] == "Admissions Handbook"
    assert data[0]["section_title"] == "Admissions"
    assert data[0]["heading_path"] == "Handbook > Admissions"
    assert data[0]["metadata_json"]["citation_label"] == "Admissions Handbook"


def test_cross_tenant_chunks_are_never_returned(client: TestClient) -> None:
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
    chunk_a_id = add_embedded_chunk(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
        content="shared query text",
        title="Alpha Source",
    )
    chunk_b_id = add_embedded_chunk(
        client,
        organisation_id=org_b_id,
        workspace_id=workspace_b_id,
        content="shared query text",
        title="Beta Source",
    )

    response = search(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
        email="alpha-viewer@example.test",
        role="viewer",
        query="shared query text",
    )

    returned_ids = [item["chunk_id"] for item in response.json()["data"]]
    assert returned_ids == [chunk_a_id]
    assert chunk_b_id not in returned_ids


def test_non_member_is_denied_search(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="alpha-viewer@example.test",
        role="viewer",
    )
    seed_tenant(
        client,
        organisation_name="Beta Clinic",
        organisation_slug="beta",
        user_email="beta-viewer@example.test",
        role="viewer",
    )

    response = search(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="beta-viewer@example.test",
        role="viewer",
        query="admissions",
    )

    assert response.status_code == 403


def test_viewer_is_allowed_search_under_current_read_rbac(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = search(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="anything",
    )

    assert response.status_code == 200


def test_no_embedded_chunks_returns_empty_result(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    add_embedded_chunk(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        content="not embedded",
        title="Draft Source",
        embedded=False,
    )

    response = search(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="not embedded",
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_search_limit_is_applied(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    for index in range(3):
        add_embedded_chunk(
            client,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            content=f"admissions information {index}",
            title=f"Source {index}",
            chunk_index=index,
        )

    response = search(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="admissions information",
        limit=2,
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
    assert response.json()["meta"]["limit"] == 2
