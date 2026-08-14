"""Unit tests for app.services.retrieval_v3 (Retrieval & Answer Pipeline V3
experiment, docs/future/RetrievalOptimisation.md Part 5/7/13) - hybrid
candidate generation with provenance preserved end to end, and the optional
retrieval cache integration."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.reranking import RerankedCandidate, RerankOutcome
from app.services.retrieval_cache import CachedRetrievalEntry, InMemoryRetrievalCacheStore, RetrievalCacheKeyParts
from app.services.retrieval_v3 import assemble_v3_retrieval_context


class _ControlledEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.dimension = 2
        self.provider_name = "controlled-test"
        self.model_name = "controlled-test-v1"

    def embed(self, text: str) -> list[float]:
        return self.vectors.get(text, [0.0, 0.0])


class _StubReranker:
    provider_name = "stub"
    model_name = "stub-v1"

    def rerank(self, *, query: str, candidates, top_k: int) -> RerankOutcome:
        reranked = [
            RerankedCandidate(match=candidate, dense_score=candidate.score, dense_rank=index + 1, rerank_score=1.0 - index * 0.1, rerank_rank=index + 1)
            for index, candidate in enumerate(candidates)
        ]
        return RerankOutcome(candidates=reranked[:top_k], status="ok", provider_name=self.provider_name, model_name=self.model_name, latency_ms=1)


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


def _seed_chunk(db: Session, *, organisation_id: str, workspace_id: str, key: str, content: str, provider: _ControlledEmbeddingProvider) -> str:
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
    return chunk.id


def _kwargs(organisation_id: str, workspace_id: str, provider) -> dict:
    return dict(
        organisation_id=organisation_id, workspace_id=workspace_id, provider=provider, document_ids=None,
        dense_pool_size=10, lexical_pool_size=10, rrf_k=60, fused_pool_size=10,
        reranker=None, reranker_top_k=10, reranker_fail_loud=False,
        max_context_chunks=10, max_context_chars=2000,
    )


def test_provenance_is_populated_for_dense_and_lexical_matches(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="prov")
    provider = _ControlledEmbeddingProvider({
        "SKU ZX-4471-Q availability": [1.0, 0.0],
        "lexical exact match content mentioning SKU ZX-4471-Q directly": [0.0, 1.0],
    })
    chunk_id = _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="lexical", content="lexical exact match content mentioning SKU ZX-4471-Q directly", provider=provider)

    result = assemble_v3_retrieval_context(db_session, query="SKU ZX-4471-Q availability", **_kwargs(organisation_id, workspace_id, provider))

    assert len(result.context.context_blocks) == 1
    block = result.context.context_blocks[0]
    assert block.chunk_id == chunk_id
    assert block.lexical_score is not None and block.lexical_score > 0  # SKU term overlap
    assert block.source_channels is not None and "lexical" in block.source_channels
    assert result.debug.lexical_candidate_count >= 1


def test_reranker_score_preserved_alongside_lexical_and_rrf_provenance(db_session: Session) -> None:
    """Part 8's explicit requirement - dense score, lexical provenance, RRF
    score, and reranker score must all remain distinct values, none
    overwriting another."""
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="rerank")
    provider = _ControlledEmbeddingProvider({
        "widget pricing": [1.0, 0.0],
        "widget pricing starts at nineteen dollars per month": [0.9, 0.1],
    })
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="pricing", content="widget pricing starts at nineteen dollars per month", provider=provider)

    kwargs = _kwargs(organisation_id, workspace_id, provider)
    kwargs["reranker"] = _StubReranker()
    result = assemble_v3_retrieval_context(db_session, query="widget pricing", **kwargs)

    block = result.context.context_blocks[0]
    assert block.dense_score is not None
    assert block.rrf_score is not None
    assert block.rerank_score is not None
    assert block.rerank_rank is not None
    assert result.debug.reranker_enabled is True
    assert result.debug.reranker_provider == "stub"


def test_empty_knowledge_scope_retrieves_zero_chunks(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="scope")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0], "content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="content", provider=provider)

    kwargs = _kwargs(organisation_id, workspace_id, provider)
    kwargs["document_ids"] = []  # explicitly empty scope - must never fall back to "everything"
    result = assemble_v3_retrieval_context(db_session, query="query", **kwargs)

    assert result.context.context_blocks == []


def test_cross_tenant_chunks_never_retrieved(db_session: Session) -> None:
    org_a, ws_a = _seed_tenant(db_session, suffix="tenant-a")
    org_b, ws_b = _seed_tenant(db_session, suffix="tenant-b")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0], "tenant b secret content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=org_b, workspace_id=ws_b, key="secret", content="tenant b secret content", provider=provider)

    result = assemble_v3_retrieval_context(db_session, query="query", **_kwargs(org_a, ws_a, provider))

    assert result.context.context_blocks == []


def test_cache_hit_skips_full_pipeline_and_rebuilds_from_current_content(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="cache")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0], "content": [1.0, 0.0]})
    chunk_id = _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="content", provider=provider)

    store = InMemoryRetrievalCacheStore()
    key_parts = RetrievalCacheKeyParts(
        query="query", organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=None,
        knowledge_revision="rev1", embedding_provider=provider.provider_name, embedding_model=provider.model_name, retrieval_strategy_version="v3",
    )

    kwargs = _kwargs(organisation_id, workspace_id, provider)
    first = assemble_v3_retrieval_context(db_session, query="query", cache_store=store, cache_key_parts=key_parts, **kwargs)
    assert first.cache_hit is False
    assert store.stats()["cache_miss_count"] == 1

    second = assemble_v3_retrieval_context(db_session, query="query", cache_store=store, cache_key_parts=key_parts, **kwargs)
    assert second.cache_hit is True
    assert store.stats()["cache_hit_count"] == 1
    assert second.context.context_blocks[0].chunk_id == chunk_id


def test_cache_miss_when_key_parts_differ() -> None:
    store = InMemoryRetrievalCacheStore()
    entry = CachedRetrievalEntry(chunk_ids=("c1",), document_ids=("d1",), scores=(0.9,), cached_at=0.0)
    key_a = RetrievalCacheKeyParts(query="q", organisation_id="org1", workspace_id="ws1", assistant_id=None, knowledge_revision="rev1", embedding_provider="p", embedding_model="m", retrieval_strategy_version="v3")
    key_b = RetrievalCacheKeyParts(query="q", organisation_id="org1", workspace_id="ws1", assistant_id=None, knowledge_revision="rev2", embedding_provider="p", embedding_model="m", retrieval_strategy_version="v3")
    store.set(key_a.cache_key(), entry, ttl_seconds=60)
    assert store.get(key_b.cache_key()) is None  # different knowledge_revision - a knowledge update must invalidate stale entries
