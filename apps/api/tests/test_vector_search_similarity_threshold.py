"""Unit tests for the `min_similarity_score` retrieval filter added in
app.services.vector_search.search_embedded_chunks.

These deliberately use a hand-crafted embedding provider (fixed vectors per
exact input string) rather than the bundled `LocalMockEmbeddingProvider`.
`LocalMockEmbeddingProvider` hashes text with SHA-256, which has no semantic
content: empirically, a query's cosine similarity to its genuinely correct
chunk is not reliably higher than its similarity to an unrelated chunk (see
docs/04_Engineering/Evaluation_Task_Specification.md, Phase 8 finding). Using
controlled vectors here proves the *filtering mechanism* itself is correct,
independent of whether any particular embedding provider's scores are
meaningful.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.vector_search import search_embedded_chunks


@dataclass(frozen=True)
class ControlledEmbeddingProvider:
    """Maps exact input text to a pre-registered vector so a test can force
    an exact, known cosine-similarity score between a query and a chunk."""

    vectors: dict[str, list[float]] = field(default_factory=dict)
    dimension: int = 3
    provider_name: str = "controlled-test"
    model_name: str = "controlled-test-v1"

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


def _seed_chunk(db: Session, *, organisation_id: str, workspace_id: str, key: str, content: str, provider: ControlledEmbeddingProvider) -> str:
    document = Document(organisation_id=organisation_id, workspace_id=workspace_id, title=key, source_type="txt", source_key=f"{key}.txt", status="ready")
    db.add(document)
    db.flush()
    version = DocumentVersion(organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, version_number=1, checksum=f"checksum-{key}", processing_status="ready")
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


def test_min_similarity_score_excludes_low_scoring_matches(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="threshold")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0, 0.0],
        "relevant content": [1.0, 0.0, 0.0],  # cosine similarity to query = 1.0
        "irrelevant content": [-1.0, 0.0, 0.0],  # cosine similarity to query = -1.0
    })
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="relevant", content="relevant content", provider=provider)
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="irrelevant", content="irrelevant content", provider=provider)

    unfiltered = search_embedded_chunks(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider,
    )
    assert {match.source_title for match in unfiltered} == {"relevant", "irrelevant"}

    filtered = search_embedded_chunks(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider,
        min_similarity_score=0.5,
    )
    assert [match.source_title for match in filtered] == ["relevant"]


def test_min_similarity_score_boundary_is_inclusive(db_session: Session) -> None:
    """A chunk scoring exactly the threshold value must pass (>=, not >) -
    otherwise the documented threshold value would not behave as advertised
    at its own boundary."""
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="boundary")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0],
        "exact match content": [0.6, 0.8],  # cosine similarity to [1,0] is exactly 0.6
    }, dimension=2)
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="exact", content="exact match content", provider=provider)

    at_threshold = search_embedded_chunks(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider,
        min_similarity_score=0.6,
    )
    assert len(at_threshold) == 1

    just_above_threshold = search_embedded_chunks(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider,
        min_similarity_score=0.6000001,
    )
    assert just_above_threshold == []


def test_min_similarity_score_of_zero_is_a_no_op(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="noop")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0, 0.0],
        "some content": [-1.0, 0.0, 0.0],
    })
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="only-doc", content="some content", provider=provider)

    matches = search_embedded_chunks(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider,
        min_similarity_score=0.0,
    )
    assert len(matches) == 1


def test_min_similarity_score_can_exclude_every_match_leaving_none(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="all-excluded")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0, 0.0],
        "weakly related content": [0.1, 0.99, 0.0],
    })
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="weak", content="weakly related content", provider=provider)

    matches = search_embedded_chunks(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider,
        min_similarity_score=0.9,
    )
    assert matches == []
