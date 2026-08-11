"""Pure unit tests for app.services.retrieval_fusion.reciprocal_rank_fusion -
no DB involved, exercising the canonical RRF formula, dedup, provenance, and
determinism requirements directly (Retrieval V2 Phase 1,
docs/future/HybridRetrieval.md)."""

from app.services.lexical_search import LexicalSearchMatch
from app.services.retrieval_fusion import reciprocal_rank_fusion
from app.services.vector_search import VectorSearchMatch


def _vector_match(chunk_id: str, score: float = 0.9) -> VectorSearchMatch:
    return VectorSearchMatch(
        chunk_id=chunk_id, document_id=f"doc-{chunk_id}", document_version_id=f"ver-{chunk_id}",
        chunk_index=0, content=f"content {chunk_id}", score=score, source_type="txt", source_title=f"title-{chunk_id}",
        page_number=None, section_title=None, heading_path=None, metadata_json=None,
    )


def _lexical_match(chunk_id: str, score: float = 0.5) -> LexicalSearchMatch:
    return LexicalSearchMatch(
        chunk_id=chunk_id, document_id=f"doc-{chunk_id}", document_version_id=f"ver-{chunk_id}",
        chunk_index=0, content=f"content {chunk_id}", score=score, source_type="txt", source_title=f"title-{chunk_id}",
        page_number=None, section_title=None, heading_path=None, metadata_json=None,
    )


def test_empty_dense_and_lexical_returns_empty() -> None:
    result = reciprocal_rank_fusion(dense_matches=[], lexical_matches=[], k=60, top_k=10)
    assert result == []


def test_empty_dense_still_returns_lexical_only_candidates() -> None:
    lexical = [_lexical_match("a"), _lexical_match("b")]
    result = reciprocal_rank_fusion(dense_matches=[], lexical_matches=lexical, k=60, top_k=10)
    assert {c.chunk_id for c in result} == {"a", "b"}
    assert all(c.source_channels == ("lexical",) for c in result)
    assert all(c.dense_rank is None and c.dense_score is None for c in result)


def test_empty_lexical_still_returns_dense_only_candidates() -> None:
    dense = [_vector_match("a"), _vector_match("b")]
    result = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=[], k=60, top_k=10)
    assert {c.chunk_id for c in result} == {"a", "b"}
    assert all(c.source_channels == ("dense",) for c in result)
    assert all(c.lexical_rank is None and c.lexical_score is None for c in result)


def test_candidate_in_both_channels_is_deduplicated_and_ranks_higher() -> None:
    dense = [_vector_match("shared"), _vector_match("dense-only")]
    lexical = [_lexical_match("shared"), _lexical_match("lexical-only")]

    result = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=lexical, k=60, top_k=10)

    ids = [c.chunk_id for c in result]
    assert ids.count("shared") == 1
    shared = next(c for c in result if c.chunk_id == "shared")
    assert shared.source_channels == ("dense", "lexical")
    assert shared.dense_rank == 1 and shared.lexical_rank == 1
    # A candidate retrieved by both channels must score at least as high as
    # any candidate retrieved by only one - the whole point of fusion.
    assert shared.rrf_score >= max(c.rrf_score for c in result if c.chunk_id != "shared")
    assert result[0].chunk_id == "shared"


def test_lexical_only_candidate_can_enter_final_set() -> None:
    dense = [_vector_match(f"dense-{i}") for i in range(5)]
    lexical = [_lexical_match("lexical-exact")]

    result = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=lexical, k=60, top_k=10)

    assert "lexical-exact" in {c.chunk_id for c in result}


def test_dense_only_candidate_can_enter_final_set() -> None:
    dense = [_vector_match("dense-exact")]
    lexical = [_lexical_match(f"lexical-{i}") for i in range(5)]

    result = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=lexical, k=60, top_k=10)

    assert "dense-exact" in {c.chunk_id for c in result}


def test_top_k_is_enforced() -> None:
    dense = [_vector_match(f"dense-{i}") for i in range(10)]
    lexical = [_lexical_match(f"lexical-{i}") for i in range(10)]

    result = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=lexical, k=60, top_k=3)

    assert len(result) == 3


def test_deterministic_across_repeated_calls_with_tie_break() -> None:
    # Two chunks that never co-occur in either channel end up with identical
    # rrf_score (rank 1 in exactly one channel each) - the chunk_id tie-break
    # must make the ordering fully deterministic regardless of dict iteration
    # order.
    dense = [_vector_match("z-chunk")]
    lexical = [_lexical_match("a-chunk")]

    first = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=lexical, k=60, top_k=10)
    second = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=lexical, k=60, top_k=10)

    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert first[0].rrf_score == first[1].rrf_score
    assert [c.chunk_id for c in first] == sorted(c.chunk_id for c in first)


def test_rrf_score_matches_canonical_formula() -> None:
    dense = [_vector_match("only")]
    result = reciprocal_rank_fusion(dense_matches=dense, lexical_matches=[], k=60, top_k=10)
    assert result[0].rrf_score == 1.0 / (60 + 1)


def test_rejects_non_positive_k_or_top_k() -> None:
    import pytest

    with pytest.raises(ValueError):
        reciprocal_rank_fusion(dense_matches=[], lexical_matches=[], k=0, top_k=10)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion(dense_matches=[], lexical_matches=[], k=60, top_k=0)
