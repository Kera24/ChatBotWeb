from dataclasses import dataclass
from time import perf_counter

from app.core.config import settings
from app.services.embeddings import EmbeddingProvider
from app.services.lexical_search import search_lexical_chunks
from app.services.reranking import NoOpReranker, Reranker, rerank_candidates
from app.services.retrieval_fusion import FusedCandidate, reciprocal_rank_fusion
from app.services.vector_search import VectorSearchMatch, search_embedded_chunks
from sqlalchemy.orm import Session

DENSE_ONLY_STRATEGY = "dense_only"
HYBRID_RRF_STRATEGY = "hybrid_rrf"


@dataclass(frozen=True)
class RetrievalDebugInfo:
    """Non-guardrail-facing retrieval provenance for observability/evaluation
    (Retrieval V2 Phase 1, docs/future/HybridRetrieval.md) - never consulted
    by citation policy or evidence sufficiency, which only ever see
    RetrievalCitationData.score."""

    strategy: str
    dense_candidate_count: int
    lexical_candidate_count: int
    fused_candidate_count: int
    dense_latency_ms: int
    lexical_latency_ms: int
    fusion_latency_ms: int
    # Retrieval V2 Phase 2 - Reranking (docs/future/Reranking.md). All default
    # to the "disabled" shape so every existing construction site in this
    # file (and any external caller) that doesn't know about reranking keeps
    # producing byte-identical RetrievalDebugInfo values.
    reranker_enabled: bool = False
    reranker_provider: str | None = None
    reranker_model: str | None = None
    reranker_candidate_count: int = 0
    reranker_selected_count: int = 0
    reranker_latency_ms: int = 0
    reranker_status: str | None = None


@dataclass(frozen=True)
class RetrievalCitationData:
    citation_index: int
    document_id: str
    document_version_id: str
    chunk_id: str
    source_title: str
    source_type: str
    page_number: int | None
    section_title: str | None
    score: float


@dataclass(frozen=True)
class RetrievalContextBlockData(RetrievalCitationData):
    content: str
    context_text: str


@dataclass(frozen=True)
class RetrievalContextResult:
    query: str
    context_blocks: list[RetrievalContextBlockData]
    citations: list[RetrievalCitationData]
    total_context_chars: int
    retrieval_debug: RetrievalDebugInfo | None = None


def assemble_retrieval_context(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query: str,
    search_limit: int,
    max_context_chunks: int,
    max_context_chars: int,
    provider: EmbeddingProvider,
    document_ids: list[str] | None = None,
    min_similarity_score: float = 0.0,
    retrieval_strategy: str | None = None,
    dense_candidate_pool_size: int | None = None,
    lexical_candidate_pool_size: int | None = None,
    rrf_k: int | None = None,
    hybrid_final_top_k: int | None = None,
    reranker: Reranker | None = None,
    reranker_candidate_pool_size: int | None = None,
    reranker_final_top_k: int | None = None,
    reranker_fail_loud: bool = False,
) -> RetrievalContextResult:
    effective_strategy = retrieval_strategy or settings.RETRIEVAL_STRATEGY
    # NoOpReranker (the default when `reranker` is None/unset, mirroring how
    # every RAGOrchestratorDependencies field defaults to a no-op) means
    # "reranking disabled" - the dense_only branch below is then byte-for-byte
    # identical to the pre-reranking behaviour, the one-line rollback
    # guarantee (Retrieval V2 Phase 2, Part 4 requirement 7).
    reranker_active = reranker is not None and not isinstance(reranker, NoOpReranker)

    if effective_strategy != HYBRID_RRF_STRATEGY:
        effective_limit = min(search_limit, max_context_chunks)
        dense_search_limit = effective_limit
        rerank_top_k = max_context_chunks
        if reranker_active:
            # Fetch a wider dense candidate pool before reranking (Part 4
            # requirement 1) - never narrower than the non-reranked limit, so
            # enabling reranking can only add candidates for it to consider,
            # never remove ones dense_only would have kept.
            pool_size = reranker_candidate_pool_size or settings.RERANKER_DENSE_CANDIDATE_POOL_SIZE
            dense_search_limit = max(pool_size, effective_limit)
            rerank_top_k = reranker_final_top_k or settings.RERANKER_FINAL_TOP_K

        dense_started_at = perf_counter()
        dense_matches = search_embedded_chunks(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            query=query,
            limit=dense_search_limit,
            provider=provider,
            document_ids=document_ids,
            # The calibrated similarity threshold still gates the dense
            # candidate pool exactly as it does for the non-reranked
            # baseline - reranking only re-orders/re-selects among chunks
            # that already cleared it, it never loosens the threshold.
            min_similarity_score=min_similarity_score,
        )
        dense_latency_ms = _elapsed_ms(dense_started_at)

        matches = dense_matches
        rerank_outcome = None
        if reranker_active:
            rerank_outcome = rerank_candidates(
                reranker, query=query, candidates=dense_matches, top_k=rerank_top_k, fail_loud=reranker_fail_loud
            )
            matches = [candidate.match for candidate in rerank_outcome.candidates]

        result = assemble_context_from_matches(
            query=query,
            matches=matches,
            max_context_chunks=max_context_chunks,
            max_context_chars=max_context_chars,
        )
        debug = RetrievalDebugInfo(
            strategy=DENSE_ONLY_STRATEGY,
            dense_candidate_count=len(dense_matches),
            lexical_candidate_count=0,
            fused_candidate_count=len(matches),
            dense_latency_ms=dense_latency_ms,
            lexical_latency_ms=0,
            fusion_latency_ms=0,
            reranker_enabled=reranker_active,
            reranker_provider=rerank_outcome.provider_name if rerank_outcome else None,
            reranker_model=rerank_outcome.model_name if rerank_outcome else None,
            reranker_candidate_count=len(dense_matches) if reranker_active else 0,
            reranker_selected_count=len(matches) if reranker_active else 0,
            reranker_latency_ms=rerank_outcome.latency_ms if rerank_outcome else 0,
            reranker_status=rerank_outcome.status if rerank_outcome else None,
        )
        return _with_debug(result, debug)

    dense_pool_size = dense_candidate_pool_size or settings.RETRIEVAL_DENSE_CANDIDATE_POOL_SIZE
    lexical_pool_size = lexical_candidate_pool_size or settings.RETRIEVAL_LEXICAL_CANDIDATE_POOL_SIZE
    effective_rrf_k = rrf_k or settings.RETRIEVAL_RRF_K
    effective_top_k = hybrid_final_top_k or settings.RETRIEVAL_HYBRID_FINAL_TOP_K

    dense_started_at = perf_counter()
    dense_matches = search_embedded_chunks(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        query=query,
        limit=dense_pool_size,
        provider=provider,
        document_ids=document_ids,
        # Deliberately NOT applying min_similarity_score to the candidate
        # pool here (Retrieval V2 Phase 1, Phase 4 requirement): RRF fuses on
        # rank, not raw score, so a chunk a lexical query matches strongly
        # should not be excluded from the pool just because its dense
        # cosine-similarity happened to sit under the calibrated threshold.
        min_similarity_score=0.0,
    )
    dense_latency_ms = _elapsed_ms(dense_started_at)

    lexical_started_at = perf_counter()
    lexical_matches = search_lexical_chunks(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        query=query,
        limit=lexical_pool_size,
        document_ids=document_ids,
    )
    lexical_latency_ms = _elapsed_ms(lexical_started_at)

    fusion_started_at = perf_counter()
    fused = reciprocal_rank_fusion(
        dense_matches=dense_matches,
        lexical_matches=lexical_matches,
        k=effective_rrf_k,
        top_k=effective_top_k,
    )
    fusion_latency_ms = _elapsed_ms(fusion_started_at)

    matches = [_fused_to_vector_match(candidate) for candidate in fused]
    rerank_outcome = None
    if reranker_active:
        # Exploratory-only path (Retrieval V2 Phase 2, Part 10): rerank the
        # already-fused hybrid candidate pool. Never promoted by default -
        # dense_only/hybrid_rrf selection is unaffected by whether this runs.
        rerank_top_k = reranker_final_top_k or settings.RERANKER_FINAL_TOP_K
        rerank_outcome = rerank_candidates(reranker, query=query, candidates=matches, top_k=rerank_top_k, fail_loud=reranker_fail_loud)
        matches = [candidate.match for candidate in rerank_outcome.candidates]

    result = assemble_context_from_matches(
        query=query,
        matches=matches,
        max_context_chunks=max_context_chunks,
        max_context_chars=max_context_chars,
    )
    debug = RetrievalDebugInfo(
        strategy=HYBRID_RRF_STRATEGY,
        dense_candidate_count=len(dense_matches),
        lexical_candidate_count=len(lexical_matches),
        fused_candidate_count=len(fused),
        dense_latency_ms=dense_latency_ms,
        lexical_latency_ms=lexical_latency_ms,
        fusion_latency_ms=fusion_latency_ms,
        reranker_enabled=reranker_active,
        reranker_provider=rerank_outcome.provider_name if rerank_outcome else None,
        reranker_model=rerank_outcome.model_name if rerank_outcome else None,
        reranker_candidate_count=len(fused) if reranker_active else 0,
        reranker_selected_count=len(matches) if reranker_active else 0,
        reranker_latency_ms=rerank_outcome.latency_ms if rerank_outcome else 0,
        reranker_status=rerank_outcome.status if rerank_outcome else None,
    )
    return _with_debug(result, debug)


def _with_debug(result: RetrievalContextResult, debug: RetrievalDebugInfo) -> RetrievalContextResult:
    return RetrievalContextResult(
        query=result.query,
        context_blocks=result.context_blocks,
        citations=result.citations,
        total_context_chars=result.total_context_chars,
        retrieval_debug=debug,
    )


def _fused_to_vector_match(candidate: FusedCandidate) -> VectorSearchMatch:
    # Score rule (Retrieval V2 Phase 1 design decision - see
    # docs/architecture/retrieval.md and the rollout report): keep the dense
    # cosine-similarity score when a dense channel match exists, since
    # app.ai.guardrails.evidence_sufficiency's off-topic detector is
    # calibrated for that 0-1 cosine scale. The RRF score itself (a
    # different, incomparable scale) is never substituted in here - it is
    # only exposed via RetrievalDebugInfo/observability. A lexical-only
    # candidate (no dense channel) gets 0.0, a documented, honest Phase 1
    # limitation rather than a fabricated confidence value.
    score = candidate.dense_score if candidate.dense_score is not None else 0.0
    return VectorSearchMatch(
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        document_version_id=candidate.document_version_id,
        chunk_index=candidate.chunk_index,
        content=candidate.content,
        score=score,
        source_type=candidate.source_type,
        source_title=candidate.source_title,
        page_number=candidate.page_number,
        section_title=candidate.section_title,
        heading_path=candidate.heading_path,
        metadata_json=candidate.metadata_json,
    )


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def assemble_context_from_matches(
    *,
    query: str,
    matches: list[VectorSearchMatch],
    max_context_chunks: int,
    max_context_chars: int,
) -> RetrievalContextResult:
    if max_context_chunks <= 0:
        raise ValueError("max_context_chunks must be positive.")
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be positive.")

    context_blocks: list[RetrievalContextBlockData] = []
    citations: list[RetrievalCitationData] = []
    total_context_chars = 0

    for match in matches[:max_context_chunks]:
        citation_index = len(context_blocks) + 1
        prefix = _context_prefix(citation_index, match)
        remaining_chars = max_context_chars - total_context_chars
        if remaining_chars <= len(prefix):
            break

        content = match.content[: remaining_chars - len(prefix)]
        if not content:
            break
        context_text = prefix + content
        citation = RetrievalCitationData(
            citation_index=citation_index,
            document_id=match.document_id,
            document_version_id=match.document_version_id,
            chunk_id=match.chunk_id,
            source_title=match.source_title,
            source_type=match.source_type,
            page_number=match.page_number,
            section_title=match.section_title,
            score=match.score,
        )
        context_blocks.append(
            RetrievalContextBlockData(
                **citation.__dict__,
                content=content,
                context_text=context_text,
            )
        )
        citations.append(citation)
        total_context_chars += len(context_text)
        if total_context_chars >= max_context_chars:
            break

    return RetrievalContextResult(
        query=query,
        context_blocks=context_blocks,
        citations=citations,
        total_context_chars=total_context_chars,
    )


def _context_prefix(citation_index: int, match: VectorSearchMatch) -> str:
    source_parts = [match.source_title]
    if match.section_title:
        source_parts.append(match.section_title)
    if match.page_number is not None:
        source_parts.append(f"page {match.page_number}")
    return f"[{citation_index}] {' | '.join(source_parts)}\n"
