"""Reciprocal Rank Fusion for Retrieval V2 Phase 1 hybrid retrieval (see
docs/future/HybridRetrieval.md). Pure, DB-free, deterministic - takes the two
already-fetched candidate pools from app.services.vector_search and
app.services.lexical_search and combines them into one ranked list, without
knowing anything about tenants, sessions, or the ORM.

Canonical form: score(d) = sum(1 / (k + rank_i(d))) over every channel i that
retrieved d, rank_i(d) 1-based within that channel's own ranked list. Rank-
based (not score-based) specifically so dense cosine-similarity and lexical
ts_rank/term-overlap scores - which are never on a comparable scale - never
need to be normalised against each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.lexical_search import LexicalSearchMatch
from app.services.vector_search import VectorSearchMatch


@dataclass(frozen=True)
class FusedCandidate:
    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    source_type: str
    source_title: str
    page_number: int | None
    section_title: str | None
    heading_path: str | None
    metadata_json: dict | None
    dense_rank: int | None
    dense_score: float | None
    lexical_rank: int | None
    lexical_score: float | None
    rrf_score: float
    source_channels: tuple[str, ...]


def reciprocal_rank_fusion(
    *,
    dense_matches: list[VectorSearchMatch],
    lexical_matches: list[LexicalSearchMatch],
    k: int,
    top_k: int,
) -> list[FusedCandidate]:
    if k <= 0:
        raise ValueError("k must be positive.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")

    entries: dict[str, dict[str, object]] = {}

    for rank, match in enumerate(dense_matches, start=1):
        entry = entries.setdefault(match.chunk_id, {"match": match})
        entry["dense_rank"] = rank
        entry["dense_score"] = match.score

    for rank, match in enumerate(lexical_matches, start=1):
        entry = entries.setdefault(match.chunk_id, {"match": match})
        entry["lexical_rank"] = rank
        entry["lexical_score"] = match.score

    candidates: list[FusedCandidate] = []
    for chunk_id, entry in entries.items():
        dense_rank = entry.get("dense_rank")
        lexical_rank = entry.get("lexical_rank")
        rrf_score = 0.0
        channels: list[str] = []
        if dense_rank is not None:
            rrf_score += 1.0 / (k + dense_rank)
            channels.append("dense")
        if lexical_rank is not None:
            rrf_score += 1.0 / (k + lexical_rank)
            channels.append("lexical")

        source_match = entry["match"]
        candidates.append(
            FusedCandidate(
                chunk_id=chunk_id,
                document_id=source_match.document_id,
                document_version_id=source_match.document_version_id,
                chunk_index=source_match.chunk_index,
                content=source_match.content,
                source_type=source_match.source_type,
                source_title=source_match.source_title,
                page_number=source_match.page_number,
                section_title=source_match.section_title,
                heading_path=source_match.heading_path,
                metadata_json=source_match.metadata_json,
                dense_rank=dense_rank,
                dense_score=entry.get("dense_score"),
                lexical_rank=lexical_rank,
                lexical_score=entry.get("lexical_score"),
                rrf_score=rrf_score,
                source_channels=tuple(channels),
            )
        )

    # Deterministic regardless of dict-iteration order: rank by descending
    # fused score, tie-break by chunk_id so two runs over the same inputs
    # always produce the exact same ordering.
    candidates.sort(key=lambda candidate: (-candidate.rrf_score, candidate.chunk_id))
    return candidates[:top_k]
