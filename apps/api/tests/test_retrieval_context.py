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
from app.services.query_transformation import RetrievalQueryPlan
from app.services.reranking import NoOpReranker, RerankedCandidate, RerankerError, RerankOutcome
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


# --- Retrieval V2 Phase 2 - reranker wiring (docs/future/Reranking.md) ---


class _ReverseOrderReranker:
    """Deterministically reverses dense order - lets tests assert reranking
    actually changed the final selection, not just that a call happened."""

    provider_name = "fake_reverse"
    model_name = "fake-reverse-v1"

    def rerank(self, *, query, candidates, top_k):
        reversed_candidates = list(reversed(candidates))[:top_k]
        ranked = [
            RerankedCandidate(match=match, dense_score=match.score, dense_rank=len(candidates) - index, rerank_score=float(index), rerank_rank=index + 1)
            for index, match in enumerate(reversed_candidates)
        ]
        return RerankOutcome(candidates=ranked, status="ok", provider_name=self.provider_name, model_name=self.model_name, latency_ms=1)


class _FailingReranker:
    provider_name = "fake_failing"
    model_name = "fake-failing-v1"

    def rerank(self, *, query, candidates, top_k):
        raise RerankerError("simulated reranker failure")


def _seed_three_chunks(db_session: Session, *, organisation_id: str, workspace_id: str, provider: _ControlledEmbeddingProvider) -> list[str]:
    ids = []
    for key, vector in (("first", [1.0, 0.0]), ("second", [0.9, 0.1]), ("third", [0.8, 0.2])):
        provider.vectors[f"content {key}"] = vector
        ids.append(_seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key=key, content=f"content {key}", provider=provider))
    return ids


def test_reranker_disabled_by_default_is_byte_identical_to_dense_only(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="rerank-default")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0]})
    _seed_three_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, provider=provider)

    without_reranker_kwarg = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider,
    )
    with_explicit_no_op = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider, reranker=NoOpReranker(),
    )
    assert [c.chunk_id for c in without_reranker_kwarg.citations] == [c.chunk_id for c in with_explicit_no_op.citations]
    assert without_reranker_kwarg.retrieval_debug.reranker_enabled is False
    assert with_explicit_no_op.retrieval_debug.reranker_enabled is False


def test_reranker_reorders_final_selection_and_preserves_dense_score(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="rerank-reorder")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0]})
    _seed_three_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, provider=provider)

    dense_only = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider,
    )
    reranked = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider,
        reranker=_ReverseOrderReranker(),
    )

    dense_order = [c.chunk_id for c in dense_only.citations]
    reranked_order = [c.chunk_id for c in reranked.citations]
    assert reranked_order == list(reversed(dense_order))
    # Dense (cosine-similarity) scores are unchanged by reranking - only order moved.
    dense_scores_by_chunk = {c.chunk_id: c.score for c in dense_only.citations}
    for citation in reranked.citations:
        assert citation.score == dense_scores_by_chunk[citation.chunk_id]
    assert reranked.retrieval_debug.reranker_enabled is True
    assert reranked.retrieval_debug.reranker_status == "ok"
    assert reranked.retrieval_debug.reranker_provider == "fake_reverse"


def test_reranker_widens_dense_candidate_pool_before_reranking(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="rerank-pool")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0]})
    _seed_three_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, provider=provider)

    # max_context_chunks=1 would normally limit the dense search itself to 1
    # candidate - with reranking enabled, the wider candidate pool size must
    # still be used so the reranker has more than one candidate to consider.
    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=1, max_context_chunks=1, max_context_chars=2000, provider=provider,
        reranker=_ReverseOrderReranker(), reranker_candidate_pool_size=3, reranker_final_top_k=1,
    )
    assert result.retrieval_debug.reranker_candidate_count == 3
    assert len(result.context_blocks) == 1


def test_reranker_failure_falls_back_safely_by_default(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="rerank-fail-safe")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0]})
    _seed_three_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, provider=provider)

    dense_only = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider,
    )
    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider,
        reranker=_FailingReranker(),
    )
    assert [c.chunk_id for c in result.citations] == [c.chunk_id for c in dense_only.citations]
    assert result.retrieval_debug.reranker_status == "failed"


def test_reranker_failure_raises_when_fail_loud_for_evaluation(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="rerank-fail-loud")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0]})
    _seed_three_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, provider=provider)

    with pytest.raises(RerankerError):
        assemble_retrieval_context(
            db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
            search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider,
            reranker=_FailingReranker(), reranker_fail_loud=True,
        )


def test_reranker_still_respects_empty_knowledge_scope(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="rerank-scope")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0]})
    _seed_three_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query",
        search_limit=3, max_context_chunks=3, max_context_chars=2000, provider=provider,
        reranker=_ReverseOrderReranker(), document_ids=[],
    )
    assert result.context_blocks == []
    assert result.citations == []


def test_reranker_never_surfaces_a_different_organisations_documents(db_session: Session) -> None:
    org_a_id, workspace_a_id = _seed_tenant(db_session, suffix="rerank-tenant-a")
    org_b_id, workspace_b_id = _seed_tenant(db_session, suffix="rerank-tenant-b")
    provider = _ControlledEmbeddingProvider({"query": [1.0, 0.0], "content a-doc": [1.0, 0.0], "content b-doc": [1.0, 0.0]})
    document_id_a = _seed_chunk(db_session, organisation_id=org_a_id, workspace_id=workspace_a_id, key="a-doc", content="content a-doc", provider=provider)
    document_id_b = _seed_chunk(db_session, organisation_id=org_b_id, workspace_id=workspace_b_id, key="b-doc", content="content b-doc", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=org_a_id, workspace_id=workspace_a_id, query="query",
        search_limit=5, max_context_chunks=5, max_context_chars=2000, provider=provider,
        reranker=_ReverseOrderReranker(),
    )
    retrieved_document_ids = [citation.document_id for citation in result.citations]
    assert document_id_b not in retrieved_document_ids
    assert retrieved_document_ids == [document_id_a]


# --- Retrieval V2 Phase 3: query transformation / multi-query merge (docs/future/QueryRewrite.md) ---

def _plan(original: str, *retrieval_queries: str) -> RetrievalQueryPlan:
    return RetrievalQueryPlan(
        original_query=original,
        retrieval_queries=retrieval_queries or (original,),
        extracted_terms=(),
        transformation_type="deterministic",
        provider="deterministic",
        model="builtin",
        latency_ms=1,
        status="ok",
    )


def test_no_query_plan_is_byte_identical_to_pre_phase3_dense_only(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="no-plan")
    provider = _ControlledEmbeddingProvider({"the query": [1.0, 0.0], "matching content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="matching content", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider,
    )
    assert result.retrieval_debug.query_transformer_enabled is False
    assert result.retrieval_debug.query_transformer_query_count == 1
    assert len(result.context_blocks) == 1


def test_identity_single_query_plan_is_byte_identical_to_no_plan(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="identity-plan")
    provider = _ControlledEmbeddingProvider({"the query": [1.0, 0.0], "matching content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="matching content", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="the query",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider,
        query_plan=_plan("the query"),
    )
    assert result.retrieval_debug.query_transformer_enabled is False
    assert len(result.context_blocks) == 1


def test_multi_query_plan_surfaces_chunk_only_matched_by_rewritten_query(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="multi-query")
    # "original phrasing" has no semantic overlap with "canonical content" in
    # this controlled 2D embedding space (orthogonal vectors) - only the
    # rewritten query finds it.
    provider = _ControlledEmbeddingProvider({
        "original phrasing": [1.0, 0.0],
        "rewritten phrasing": [0.0, 1.0],
        "canonical content": [0.0, 1.0],
    })
    document_id = _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="canonical content", provider=provider)

    baseline = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="original phrasing",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider, min_similarity_score=0.5,
    )
    assert baseline.context_blocks == []  # the rescue case: absent from Top-K under the original query alone

    rescued = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="original phrasing",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider, min_similarity_score=0.5,
        query_plan=_plan("original phrasing", "original phrasing", "rewritten phrasing"),
    )
    assert [c.document_id for c in rescued.citations] == [document_id]
    assert rescued.retrieval_debug.query_transformer_enabled is True
    assert rescued.retrieval_debug.query_transformer_query_count == 2


def test_multi_query_merge_deduplicates_chunk_found_by_both_queries_and_keeps_max_score(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="multi-query-dedup")
    provider = _ControlledEmbeddingProvider({
        "query one": [1.0, 0.0],
        "query two": [0.6, 0.8],
        "shared content": [0.8, 0.6],
    })
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="shared content", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query one",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider, min_similarity_score=0.0,
        query_plan=_plan("query one", "query one", "query two"),
    )
    assert len(result.citations) == 1  # not duplicated even though both queries matched the same chunk
    assert result.retrieval_debug.query_transformer_raw_candidate_count == 2
    assert result.retrieval_debug.query_transformer_deduplicated_candidate_count == 1


def test_multi_query_plan_only_applies_to_dense_only_not_hybrid_rrf(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="multi-query-hybrid-scope")
    provider = _ControlledEmbeddingProvider({"query one": [1.0, 0.0], "matching content": [1.0, 0.0]})
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="matching content", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="query one",
        search_limit=5, max_context_chunks=5, max_context_chars=1000, provider=provider,
        retrieval_strategy=HYBRID_RRF_STRATEGY,
        query_plan=_plan("query one", "query one", "query two"),
    )
    # Retrieval V2 Phase 3 is scoped to dense_only only - a multi-query plan
    # passed alongside hybrid_rrf is accepted but has no effect (documented
    # scope limit, not a silent bug).
    assert result.retrieval_debug.strategy == HYBRID_RRF_STRATEGY
    assert result.retrieval_debug.query_transformer_enabled is False


def test_multi_query_plan_never_surfaces_a_different_organisations_documents(db_session: Session) -> None:
    org_a_id, workspace_a_id = _seed_tenant(db_session, suffix="multi-query-tenant-a")
    org_b_id, workspace_b_id = _seed_tenant(db_session, suffix="multi-query-tenant-b")
    provider = _ControlledEmbeddingProvider({
        "query": [1.0, 0.0], "rewritten query": [0.0, 1.0],
        "content a-doc": [1.0, 0.0], "content b-doc": [0.0, 1.0],
    })
    document_id_a = _seed_chunk(db_session, organisation_id=org_a_id, workspace_id=workspace_a_id, key="a-doc", content="content a-doc", provider=provider)
    _seed_chunk(db_session, organisation_id=org_b_id, workspace_id=workspace_b_id, key="b-doc", content="content b-doc", provider=provider)

    result = assemble_retrieval_context(
        db_session, organisation_id=org_a_id, workspace_id=workspace_a_id, query="query",
        search_limit=5, max_context_chunks=5, max_context_chars=2000, provider=provider,
        query_plan=_plan("query", "query", "rewritten query"),
    )
    retrieved_document_ids = [citation.document_id for citation in result.citations]
    assert retrieved_document_ids == [document_id_a]
