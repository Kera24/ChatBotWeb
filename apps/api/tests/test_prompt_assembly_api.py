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
    original_version = settings.PROMPT_VERSION
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "prompt-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    object.__setattr__(settings, "PROMPT_VERSION", "prompt-test-v1")

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)
    object.__setattr__(settings, "PROMPT_VERSION", original_version)
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
) -> str:
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
            section_title="Admissions",
            status="ready",
            embedding_provider="local-mock",
            embedding_model="prompt-test",
            embedding_dimension=8,
            embedding_created_at=datetime.now(timezone.utc),
        )
        db.add(chunk)
        db.commit()
        return chunk.id


def prompt(
    client: TestClient,
    *,
    organisation_id: str,
    workspace_id: str,
    email: str,
    role: str,
    query: str,
):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/prompt",
        params={"organisation_id": organisation_id},
        json={"query": query, "limit": 5, "max_context_chars": 1000},
        headers=dev_headers(email, role),
    )


def test_prompt_includes_retrieved_context(client: TestClient) -> None:
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

    response = prompt(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="applications close in december",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["prompt_version"] == "prompt-test-v1"
    assert "applications close in december" in data["user_prompt"]
    assert "[1] Admissions Handbook" in data["user_prompt"]
    assert len(data["context_blocks"]) == 1


def test_prompt_includes_citation_rules(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = prompt(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="What is the intake date?",
    )

    system_prompt = response.json()["data"]["system_prompt"]
    assert "Cite every factual claim" in system_prompt
    assert "numbered citation" in system_prompt
    assert "Never cite a source that does not support the claim" in system_prompt


def test_prompt_includes_safe_fallback_and_no_guessing_rules(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = prompt(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="viewer@example.test",
        role="viewer",
        query="Unknown question",
    )

    data = response.json()["data"]
    assert "does not contain enough information" in data["system_prompt"]
    assert "Do not guess" in data["user_prompt"]
    assert "No retrieved context was available" in data["user_prompt"]


def test_prompt_cross_tenant_isolation(client: TestClient) -> None:
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
    chunk_a = add_embedded_chunk(
        client,
        organisation_id=org_a_id,
        workspace_id=workspace_a_id,
        content="shared context",
        title="Alpha Source",
    )
    chunk_b = add_embedded_chunk(
        client,
        organisation_id=org_b_id,
        workspace_id=workspace_b_id,
        content="shared context",
        title="Beta Source",
    )

    response = prompt(
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
    assert "Beta Source" not in response.json()["data"]["user_prompt"]


def test_non_member_is_denied_prompt_assembly(client: TestClient) -> None:
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

    response = prompt(
        client,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        email="beta-viewer@example.test",
        role="viewer",
        query="admissions",
    )

    assert response.status_code == 403


def test_empty_context_creates_fallback_ready_prompt(client: TestClient) -> None:
    organisation_id, workspace_id, _user_id = seed_tenant(
        client,
        organisation_name="Alpha College",
        organisation_slug="alpha",
        user_email="viewer@example.test",
        role="viewer",
    )

    response = prompt(
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
    assert "No retrieved context was available" in data["user_prompt"]
    assert "knowledge base does not contain enough information" in data["user_prompt"]
