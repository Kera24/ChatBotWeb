"""Unit tests for app.services.retrieval_context.assemble_retrieval_context's
Retrieval V2 Phase 1 strategy switch (docs/future/HybridRetrieval.md):
dense_only stays the untouched rollback baseline, hybrid_rrf fuses dense +
lexical candidates, and knowledge-scope isolation holds under both."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.retrieval_context import DENSE_ONLY_STRATEGY, HYBRID_RRF_STRATEGY, assemble_retrieval_context


class _ControlledEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.dimension = 2
        self.provider_name = "controlled-test"
        self.model_name = "controlled-test-v1"

    def embed(self, text: str) -> list[float]:
        return self.vectors.get(text, [0.0, 0.0])


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
    db: Session, *, organisation_id: str, workspace_id: str, key: str, content: str, provider: _ControlledEmbeddingProvider,
) -> str:
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


def test_dense_only_is_the_default_strategy(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="default")
    provider = _ControlledEmbeddingProvider({"the query": [1.0, 0.0], "matching content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="matching content", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider,
    )

    assert result.retrieval_debug is not None
    assert result.retrieval_debug.strategy == DENSE_ONLY_STRATEGY
    assert result.retrieval_debug.lexical_candidate_count == 0
    assert len(result.context_blocks) == 1


def test_hybrid_rrf_surfaces_lexical_only_match_that_dense_alone_would_miss(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="hybrid")
    # The lexical-exact chunk has an orthogonal embedding (cosine similarity
    # 0.0 against the query) - dense_only with a nonzero threshold would
    # never surface it, but its content lexically matches the query exactly.
    provider = _ControlledEmbeddingProvider({
        "SKU ZX-4471-Q availability": [1.0, 0.0],
        "lexical exact match content mentioning SKU ZX-4471-Q directly": [0.0, 1.0],
        "semantically similar but no exact term overlap": [0.99, 0.01],
    })
    lexical_doc_id = _seed_chunk(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="lexical",
        content="lexical exact match content mentioning SKU ZX-4471-Q directly", provider=provider,
    )
    _seed_chunk(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="semantic",
        content="semantically similar but no exact term overlap", provider=provider,
    )

    dense_only = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="SKU ZX-4471-Q availability",
        search_limit=5, max_context_chunks=5, max_context_chars=2000, provider=provider,
        min_similarity_score=0.5, retrieval_strategy=DENSE_ONLY_STRATEGY,
    )
    assert lexical_doc_id not in [c.document_id for c in dense_only.citations]

    hybrid = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="SKU ZX-4471-Q availability",
        search_limit=5, max_context_chunks=5, max_context_chars=2000, provider=provider,
        min_similarity_score=0.5, retrieval_strategy=HYBRID_RRF_STRATEGY,
    )
    assert lexical_doc_id in [c.document_id for c in hybrid.citations]
    assert hybrid.retrieval_debug is not None
    assert hybrid.retrieval_debug.strategy == HYBRID_RRF_STRATEGY
    assert hybrid.retrieval_debug.lexical_candidate_count >= 1


def test_hybrid_rrf_respects_empty_knowledge_scope(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="hybrid-scope")
    provider = _ControlledEmbeddingProvider({"the query": [1.0, 0.0], "some content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="some content", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider,
        retrieval_strategy=HYBRID_RRF_STRATEGY, document_ids=[],
    )

    assert result.context_blocks == []
    assert result.citations == []
