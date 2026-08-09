"""Regression test for a real retrieval defect found while building the
PostgreSQL/pgvector production-path integration tier
(tests/test_vector_search_postgres_integration.py): archiving a document
(app.services.document_lifecycle.transition_document_status's "archived"
transition) only sets Document.status/archived_at - it never touches
active_document_version_id or chunk status - so neither
app.services.vector_search._search_sqlite nor _search_postgresql excluded an
archived document's chunks from retrieval. Fixed by adding a
`Document.status == "ready"` condition to both backends. This file covers
the SQLite backend (`_search_sqlite`, exercised via the default in-memory
engine every other unit test in this suite uses); the Postgres-side
regression test lives alongside the rest of that integration tier."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.vector_search import search_embedded_chunks


class _ControlledEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.dimension = 2
        self.provider_name = "controlled-test"
        self.model_name = "controlled-test-v1"

    def embed(self, text: str) -> list[float]:
        return self.vectors[text]


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db: Session, *, suffix: str) -> tuple[str, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation.id, workspace.id


def _seed_chunk(
    db: Session, *, organisation_id: str, workspace_id: str, key: str, content: str,
    provider: _ControlledEmbeddingProvider, document_status: str,
) -> str:
    document = Document(
        organisation_id=organisation_id, workspace_id=workspace_id, title=key, source_type="txt",
        source_key=f"{key}.txt", status=document_status,
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id,
        version_number=1, checksum=f"checksum-{key}", processing_status="ready",
    )
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    chunk = Chunk(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()),
        source_type="txt", source_title=key, status="ready",
        embedding_provider=provider.provider_name, embedding_model=provider.model_name, embedding_dimension=provider.dimension,
        embedding_created_at=datetime.now(timezone.utc),
    )
    db.add(chunk)
    db.commit()
    return document.id


def test_archived_document_is_excluded_from_retrieval(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="archived")
    provider = _ControlledEmbeddingProvider({
        "the query": [1.0, 0.0], "archived content": [1.0, 0.0], "active content": [1.0, 0.0],
    })
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="archived", content="archived content", provider=provider, document_status="archived")
    active_doc_id = _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="active", content="active content", provider=provider, document_status="ready")

    matches = search_embedded_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider)

    assert len(matches) == 1
    assert matches[0].document_id == active_doc_id


@pytest.mark.parametrize("status", ["uploaded", "processing", "failed", "expired", "deleted"])
def test_non_ready_document_statuses_are_excluded_from_retrieval(db_session: Session, status: str) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix=f"status-{status}")
    provider = _ControlledEmbeddingProvider({"the query": [1.0, 0.0], "some content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="some content", provider=provider, document_status=status)

    matches = search_embedded_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider)

    assert matches == []


def test_ready_document_is_still_retrievable(db_session: Session) -> None:
    """Sanity check alongside the exclusion tests above - the fix must not
    accidentally exclude the normal, fully-active case."""
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="ready")
    provider = _ControlledEmbeddingProvider({"the query": [1.0, 0.0], "some content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="some content", provider=provider, document_status="ready")

    matches = search_embedded_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider)

    assert len(matches) == 1
