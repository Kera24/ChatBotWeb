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
    original_chunks = settings.RETRIEVAL_MAX_CONTEXT_CHUNKS
    original_chars = settings.RETRIEVAL_MAX_CONTEXT_CHARS
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "retrieval-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHUNKS", 5)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHARS", 1000)

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHUNKS", original_chunks)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHARS", original_chars)
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
    page_number: int | None = 1,
    section_title: str | None = "Admissions",
) -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        document = Document(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=title,
            source_type="txt",
            source_key=f"{title}.txt",
            status="ready",
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            version_number=1,
            checksum=f"checksum-{title}",
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
            chunk_index=0,
            content=content,
            content_hash=f"hash-{title}",
            token_count=len(content.split()),
            source_type="txt",
            source_title=title,
            page_number=page_number,
            section_title=section_title,
            status="ready",
            embedding_provider="local-mock",
            embedding_model="retrieval-test",
            embedding_dimension=8,
            embedding_created_at=datetime.now(timezone.utc),
        )
        db.add(chunk)
        db.commit()
        return document.id, version.id, chunk.id


def retrieve(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    email: str,
    role: str,
    query: str,
    limit: int = 5,
    max_context_chars: int | None = None,
):
    body = {"query": query, "limit": limit}
    if max_context_chars is not None:
        body["max_context_chars"] = max_context_chars
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/context",
        params={"organisation_id": organisation_id},
        json=body,
        headers=dev_headers(email, role),
    )


def test_successful_context_assembly(client: TestClient) -> None:
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
        content="applications close in december",
        title="Admissions Handbook",
    )

    response = retrieve(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="applications close in december",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["query"] == "applications close in december"
    assert len(data["context_blocks"]) == 1
    assert data["context_blocks"][0]["context_text"].startswith("[1] Admissions Handbook")
    assert "applications close in december" in data["context_blocks"][0]["context_text"]
    assert data["total_context_chars"] == len(data["context_blocks"][0]["context_text"])


def test_max_context_character_limit_is_respected(client: TestClient) -> None:
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
        content="applications " * 50,
        title="Admissions Handbook",
    )

    response = retrieve(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="applications",
        max_context_chars=80,
    )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["total_context_chars"] <= 80
    assert len(data["context_blocks"]) == 1
    assert len(data["context_blocks"][0]["content"]) < len("applications " * 50)


def test_citation_metadata_is_included(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )
    document_id, version_id, chunk_id = add_embedded_chunk(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        content="orientation begins monday",
        title="Student Guide",
        page_number=7,
        section_title="Orientation",
    )

    response = retrieve(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="orientation begins monday",
    )

    citation = response.json()["data"]["citations"][0]
    assert citation["citation_index"] == 1
    assert citation["document_id"] == document_id
    assert citation["document_version_id"] == version_id
    assert citation["chunk_id"] == chunk_id
    assert citation["source_title"] == "Student Guide"
    assert citation["source_type"] == "txt"
    assert citation["page_number"] == 7
    assert citation["section_title"] == "Orientation"
    assert citation["score"] == pytest.approx(1.0)


def test_cross_tenant_context_isolation(client: TestClient) -> None:
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
    _doc_a, _version_a, chunk_a = add_embedded_chunk(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
        content="shared context",
        title="Alpha Source",
    )
    _doc_b, _version_b, chunk_b = add_embedded_chunk(
        client,
        organisation_id=org_b_id,
        workspace_id=workspace_b_id,
        content="shared context",
        title="Beta Source",
    )

    response = retrieve(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
        email="alpha-viewer@example.test",
        role="viewer",
        query="shared context",
    )

    returned_ids = [citation["chunk_id"] for citation in response.json()["data"]["citations"]]
    assert returned_ids == [chunk_a]
    assert chunk_b not in returned_ids


def test_non_member_is_denied_context_retrieval(client: TestClient) -> None:
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

    response = retrieve(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="beta-viewer@example.test",
        role="viewer",
        query="admissions",
    )

    assert response.status_code == 403


def test_empty_search_result_returns_empty_context(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = retrieve(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="nothing indexed",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["context_blocks"] == []
    assert data["citations"] == []
    assert data["total_context_chars"] == 0
