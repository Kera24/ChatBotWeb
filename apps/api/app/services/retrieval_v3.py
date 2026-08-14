"""Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md) -
hybrid candidate generation with full per-chunk provenance preserved end to
end. Deliberately NOT a rewrite of app.services.retrieval_context: every
retrieval primitive here (`search_embedded_chunks`, `search_lexical_chunks`,
`reciprocal_rank_fusion`, `rerank_candidates`, `assemble_context_from_matches`)
is the exact same, unmodified function `assemble_retrieval_context()` already
uses - this module only composes them differently, keeping the FusedCandidate/
RerankedCandidate provenance that `assemble_retrieval_context()`'s
`_fused_to_vector_match()` conversion step intentionally discards (a single
`score` field is all evidence_sufficiency's off-topic detector needs on that
code path - see its own docstring). V3's new Evidence Confidence model needs
dense score, lexical support, and reranker score as independent signals, so
this module threads all of them through
`assemble_context_from_matches`'s additive `provenance_by_chunk_id` parameter
instead.

`assemble_retrieval_context()` itself is completely untouched by this module
and remains the production baseline's exact code path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.services.lexical_search import search_lexical_chunks
from app.services.reranking import NoOpReranker, Reranker, rerank_candidates
from app.services.retrieval_cache import CachedRetrievalEntry, RetrievalCacheKeyParts, RetrievalCacheStore
from app.services.retrieval_context import (
    RetrievalContextResult,
    _fused_to_vector_match,  # reused deliberately - see this module's docstring
    assemble_context_from_matches,
)
from app.services.retrieval_fusion import FusedCandidate, reciprocal_rank_fusion
from app.services.embeddings import EmbeddingProvider
from app.services.vector_search import VectorSearchMatch, search_embedded_chunks

RETRIEVAL_V3_STRATEGY = "hybrid_rrf_v3"


@dataclass(frozen=True)
class V3RetrievalDebugInfo:
    dense_candidate_count: int
    lexical_candidate_count: int
    fused_candidate_count: int
    reranker_enabled: bool
    reranker_status: str | None
    reranker_provider: str | None
    reranker_model: str | None


@dataclass(frozen=True)
class V3RetrievalResult:
    context: RetrievalContextResult
    debug: V3RetrievalDebugInfo
    cache_hit: bool = False


def _match_from_chunk_row(chunk: Chunk, *, score: float) -> VectorSearchMatch:
    return VectorSearchMatch(
        chunk_id=chunk.id, document_id=chunk.document_id, document_version_id=chunk.document_version_id,
        chunk_index=chunk.chunk_index, content=chunk.content, score=score, source_type=chunk.source_type,
        source_title=chunk.source_title, page_number=chunk.page_number, section_title=chunk.section_title,
        heading_path=chunk.heading_path, metadata_json=chunk.metadata_json,
    )


def _rebuild_from_cache(db: Session, *, query: str, entry: CachedRetrievalEntry, max_context_chunks: int, max_context_chars: int) -> RetrievalContextResult:
    """Cache HIT path (Part 13's retrieval cache): re-fetches the cached
    chunk ids' current content by primary key (a bounded, indexed lookup -
    never re-runs embedding, lexical search, fusion, or reranking) and
    rebuilds context/citations exactly as assemble_context_from_matches
    always does. Deliberately re-reads content fresh rather than caching it,
    so a chunk edited between the cache write and this read is never served
    stale text - only the RANKING/selection is cached, not the content."""
    rows = {row.id: row for row in db.execute(select(Chunk).where(Chunk.id.in_(entry.chunk_ids))).scalars().all()}
    score_by_id = dict(zip(entry.chunk_ids, entry.scores, strict=True))
    matches = [_match_from_chunk_row(rows[chunk_id], score=score_by_id[chunk_id]) for chunk_id in entry.chunk_ids if chunk_id in rows]
    return assemble_context_from_matches(query=query, matches=matches, max_context_chunks=max_context_chunks, max_context_chars=max_context_chars)


def _provenance_from_fused(fused: list[FusedCandidate]) -> dict[str, dict]:
    return {
        candidate.chunk_id: {
            "dense_score": candidate.dense_score,
            "dense_rank": candidate.dense_rank,
            "lexical_score": candidate.lexical_score,
            "lexical_rank": candidate.lexical_rank,
            "rrf_score": candidate.rrf_score,
            "source_channels": candidate.source_channels,
        }
        for candidate in fused
    }


def assemble_v3_retrieval_context(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query: str,
    provider: EmbeddingProvider,
    document_ids: list[str] | None,
    dense_pool_size: int,
    lexical_pool_size: int,
    rrf_k: int,
    fused_pool_size: int,
    reranker: Reranker | None,
    reranker_top_k: int,
    reranker_fail_loud: bool,
    max_context_chunks: int,
    max_context_chars: int,
    cache_store: RetrievalCacheStore | None = None,
    cache_key_parts: RetrievalCacheKeyParts | None = None,
    cache_ttl_seconds: int = 300,
) -> V3RetrievalResult:
    """Bounded candidate pools throughout (Part 5's explicit "do not allow
    uncontrolled candidate explosion") - dense_pool_size/lexical_pool_size
    cap what each channel fetches, fused_pool_size caps what survives RRF
    fusion before reranking/context assembly, exactly mirroring
    assemble_retrieval_context's hybrid_rrf branch's own bounding, just with
    provenance preserved past this point.

    Same tenant/workspace/document-scope/ready-status/archived-exclusion
    filtering as the baseline - both search_embedded_chunks and
    search_lexical_chunks are the identical, unmodified functions the
    production dense_only/hybrid_rrf paths call; this module changes
    composition, never the security-critical WHERE-clause filtering inside
    either.

    `cache_store`/`cache_key_parts` are both optional and default to None
    (no caching - identical behaviour to before this parameter existed).
    When both are provided (app.services.retrieval_cache, Part 13), a HIT
    skips dense search/lexical search/fusion/reranking entirely and rebuilds
    context from the cached chunk ids' CURRENT content; a MISS runs the full
    pipeline as normal and writes the result back. Cache hits carry less
    per-chunk provenance (dense/lexical/rrf/rerank scores are not
    persisted, only the final selection + score) - a deliberate, documented
    trade-off, not a correctness issue: evidence sufficiency itself never
    depends on this provenance, only Evidence Confidence's signal richness
    is reduced on a cached response."""
    if cache_store is not None and cache_key_parts is not None:
        cached = cache_store.get(cache_key_parts.cache_key())
        if cached is not None:
            context = _rebuild_from_cache(db, query=query, entry=cached, max_context_chunks=max_context_chunks, max_context_chars=max_context_chars)
            return V3RetrievalResult(
                context=context,
                debug=V3RetrievalDebugInfo(
                    dense_candidate_count=0, lexical_candidate_count=0, fused_candidate_count=len(cached.chunk_ids),
                    reranker_enabled=False, reranker_status="cache_hit", reranker_provider=None, reranker_model=None,
                ),
                cache_hit=True,
            )

    dense_matches = search_embedded_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query=query,
        limit=dense_pool_size, provider=provider, document_ids=document_ids,
        # Same rationale as assemble_retrieval_context's hybrid_rrf branch:
        # RRF fuses on rank, not raw score, so the similarity floor is not
        # applied to the candidate pool itself.
        min_similarity_score=0.0,
    )
    lexical_matches = search_lexical_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query=query,
        limit=lexical_pool_size, document_ids=document_ids,
    )
    fused = reciprocal_rank_fusion(dense_matches=dense_matches, lexical_matches=lexical_matches, k=rrf_k, top_k=fused_pool_size)
    provenance_by_chunk_id = _provenance_from_fused(fused)

    candidate_matches = [_fused_to_vector_match(candidate) for candidate in fused]

    reranker_active = reranker is not None and not isinstance(reranker, NoOpReranker)
    rerank_outcome = None
    final_matches = candidate_matches
    if reranker_active:
        rerank_outcome = rerank_candidates(reranker, query=query, candidates=candidate_matches, top_k=reranker_top_k, fail_loud=reranker_fail_loud)
        final_matches = [c.match for c in rerank_outcome.candidates]
        for reranked in rerank_outcome.candidates:
            entry = provenance_by_chunk_id.setdefault(reranked.match.chunk_id, {})
            entry["rerank_score"] = reranked.rerank_score
            entry["rerank_rank"] = reranked.rerank_rank

    context = assemble_context_from_matches(
        query=query, matches=final_matches, max_context_chunks=max_context_chunks, max_context_chars=max_context_chars,
        provenance_by_chunk_id=provenance_by_chunk_id,
    )
    debug = V3RetrievalDebugInfo(
        dense_candidate_count=len(dense_matches), lexical_candidate_count=len(lexical_matches), fused_candidate_count=len(fused),
        reranker_enabled=reranker_active,
        reranker_status=rerank_outcome.status if rerank_outcome else None,
        reranker_provider=rerank_outcome.provider_name if rerank_outcome else None,
        reranker_model=rerank_outcome.model_name if rerank_outcome else None,
    )
    if cache_store is not None and cache_key_parts is not None and context.context_blocks:
        cache_store.set(
            cache_key_parts.cache_key(),
            CachedRetrievalEntry(
                chunk_ids=tuple(b.chunk_id for b in context.context_blocks),
                document_ids=tuple(b.document_id for b in context.context_blocks),
                scores=tuple(b.score for b in context.context_blocks),
                cached_at=time.time(),
            ),
            ttl_seconds=cache_ttl_seconds,
        )
    return V3RetrievalResult(context=context, debug=debug)
