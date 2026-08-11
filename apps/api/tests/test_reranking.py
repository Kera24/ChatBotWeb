"""Unit tests for app.services.reranking - the provider-independent
reranking abstraction (Retrieval V2 Phase 2, docs/future/Reranking.md).

CrossEncoderReranker is tested against a fake, injected model object rather
than a real sentence-transformers model (not assumed to be installed in
every dev/CI environment - see the Reranker model-selection report) so the
ranking/timeout/malformed-output/failure-handling logic is still fully
covered without a live model dependency.
"""

from __future__ import annotations

import time

import pytest

from app.services.reranking import (
    CROSS_ENCODER_PROVIDER,
    NO_RERANKER_PROVIDER,
    CrossEncoderReranker,
    NoOpReranker,
    RerankerError,
    RerankerMalformedOutputError,
    RerankerTimeoutError,
    RerankerUnavailableError,
    build_reranker,
    rerank_candidates,
)
from app.services.vector_search import VectorSearchMatch


def _match(chunk_id: str, *, document_id: str | None = None, score: float, content: str = "content") -> VectorSearchMatch:
    return VectorSearchMatch(
        chunk_id=chunk_id,
        document_id=document_id or f"doc-{chunk_id}",
        document_version_id=f"ver-{chunk_id}",
        chunk_index=0,
        content=content,
        score=score,
        source_type="document",
        source_title=f"Title {chunk_id}",
        page_number=None,
        section_title=None,
        heading_path=None,
        metadata_json=None,
    )


class FakeCrossEncoderModel:
    """Stands in for sentence_transformers.CrossEncoder - .predict(pairs)
    returns one score per (query, content) pair, in order."""

    def __init__(self, scores=None, *, raise_error: Exception | None = None, sleep_seconds: float = 0.0, wrong_count: bool = False):
        self.scores = scores
        self.raise_error = raise_error
        self.sleep_seconds = sleep_seconds
        self.wrong_count = wrong_count
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs):
        self.calls.append(list(pairs))
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        if self.raise_error is not None:
            raise self.raise_error
        if self.wrong_count:
            return [0.1]
        if self.scores is not None:
            return list(self.scores)
        # Default: reverse input order score (last pair scores highest).
        return [float(i) for i in range(len(pairs))]


def _cross_encoder_with(model: FakeCrossEncoderModel, **kwargs) -> CrossEncoderReranker:
    reranker = CrossEncoderReranker(model_name="fake-cross-encoder", **kwargs)
    reranker._model = model  # bypass lazy-load, inject the fake directly
    return reranker


# --- NoOpReranker ---

def test_no_op_reranker_preserves_dense_order_and_scores() -> None:
    candidates = [_match("a", score=0.9), _match("b", score=0.5), _match("c", score=0.3)]
    outcome = NoOpReranker().rerank(query="q", candidates=candidates, top_k=10)
    assert [c.match.chunk_id for c in outcome.candidates] == ["a", "b", "c"]
    assert all(c.rerank_score is None for c in outcome.candidates)
    assert [c.match.score for c in outcome.candidates] == [0.9, 0.5, 0.3]
    assert outcome.status == "no_reranker"
    assert outcome.provider_name == NO_RERANKER_PROVIDER


def test_no_op_reranker_respects_top_k() -> None:
    candidates = [_match(str(i), score=1.0 - i * 0.1) for i in range(5)]
    outcome = NoOpReranker().rerank(query="q", candidates=candidates, top_k=2)
    assert len(outcome.candidates) == 2


def test_no_op_reranker_handles_empty_candidates() -> None:
    outcome = NoOpReranker().rerank(query="q", candidates=[], top_k=10)
    assert outcome.candidates == []


# --- CrossEncoderReranker: deterministic ranking, candidate preservation, score separation ---

def test_cross_encoder_reranks_deterministically_by_score() -> None:
    candidates = [_match("a", score=0.4), _match("b", score=0.9), _match("c", score=0.1)]
    model = FakeCrossEncoderModel(scores=[0.2, 0.9, 0.5])  # b highest, c next, a lowest
    reranker = _cross_encoder_with(model)
    outcome = reranker.rerank(query="q", candidates=candidates, top_k=10)
    assert [c.match.chunk_id for c in outcome.candidates] == ["b", "c", "a"]
    assert outcome.status == "ok"


def test_cross_encoder_preserves_original_candidate_identity() -> None:
    candidates = [_match("a", score=0.4, content="alpha"), _match("b", score=0.9, content="beta")]
    model = FakeCrossEncoderModel(scores=[0.1, 0.2])
    reranker = _cross_encoder_with(model)
    outcome = reranker.rerank(query="q", candidates=candidates, top_k=10)
    matches = {c.match.chunk_id: c.match for c in outcome.candidates}
    assert matches["a"].content == "alpha"
    assert matches["b"].content == "beta"


def test_cross_encoder_keeps_dense_score_separate_from_rerank_score() -> None:
    candidates = [_match("a", score=0.4), _match("b", score=0.9)]
    model = FakeCrossEncoderModel(scores=[0.99, 0.01])  # inverts dense order
    reranker = _cross_encoder_with(model)
    outcome = reranker.rerank(query="q", candidates=candidates, top_k=10)
    top = outcome.candidates[0]
    assert top.match.chunk_id == "a"
    assert top.match.score == 0.4  # dense score is untouched, even though "a" is now ranked first
    assert top.rerank_score == pytest.approx(0.99)
    assert top.dense_rank == 1  # "a" was already dense-rank 1 (first in the input list)
    assert top.rerank_rank == 1


def test_cross_encoder_respects_top_k() -> None:
    candidates = [_match(str(i), score=1.0) for i in range(5)]
    model = FakeCrossEncoderModel(scores=[float(i) for i in range(5)])
    reranker = _cross_encoder_with(model)
    outcome = reranker.rerank(query="q", candidates=candidates, top_k=2)
    assert len(outcome.candidates) == 2
    # Highest two fake scores are indices 4 and 3.
    assert [c.match.chunk_id for c in outcome.candidates] == ["4", "3"]


def test_cross_encoder_handles_duplicate_candidates() -> None:
    candidates = [_match("a", score=0.5, content="same"), _match("a", score=0.5, content="same")]
    model = FakeCrossEncoderModel(scores=[0.3, 0.7])
    reranker = _cross_encoder_with(model)
    outcome = reranker.rerank(query="q", candidates=candidates, top_k=10)
    assert len(outcome.candidates) == 2
    assert outcome.candidates[0].rerank_score == pytest.approx(0.7)


def test_cross_encoder_handles_empty_candidates() -> None:
    reranker = _cross_encoder_with(FakeCrossEncoderModel())
    outcome = reranker.rerank(query="q", candidates=[], top_k=10)
    assert outcome.candidates == []
    assert outcome.status == "empty_candidates"


# --- failure modes: timeout, malformed output, model unavailable ---

def test_cross_encoder_raises_timeout_error_on_slow_model() -> None:
    model = FakeCrossEncoderModel(sleep_seconds=0.3)
    reranker = _cross_encoder_with(model, timeout_seconds=0.05)
    with pytest.raises(RerankerTimeoutError):
        reranker.rerank(query="q", candidates=[_match("a", score=0.5)], top_k=10)


def test_cross_encoder_raises_malformed_output_error_on_score_count_mismatch() -> None:
    model = FakeCrossEncoderModel(wrong_count=True)
    reranker = _cross_encoder_with(model)
    with pytest.raises(RerankerMalformedOutputError):
        reranker.rerank(query="q", candidates=[_match("a", score=0.5), _match("b", score=0.4)], top_k=10)


def test_cross_encoder_wraps_model_prediction_error() -> None:
    model = FakeCrossEncoderModel(raise_error=RuntimeError("model exploded"))
    reranker = _cross_encoder_with(model)
    with pytest.raises(RerankerError):
        reranker.rerank(query="q", candidates=[_match("a", score=0.5)], top_k=10)


def test_cross_encoder_raises_unavailable_error_when_dependency_missing() -> None:
    reranker = CrossEncoderReranker(model_name="fake-cross-encoder")
    # No fake model injected and sentence_transformers is not necessarily
    # installed in this environment - either way this must raise a clear
    # RerankerUnavailableError, never a bare ImportError/AttributeError.
    with pytest.raises(RerankerUnavailableError):
        reranker._load_model()


# --- build_reranker factory ---

def test_build_reranker_none_returns_no_op() -> None:
    reranker = build_reranker(provider_name=NO_RERANKER_PROVIDER)
    assert isinstance(reranker, NoOpReranker)


def test_build_reranker_cross_encoder_requires_model_name() -> None:
    with pytest.raises(RerankerError):
        build_reranker(provider_name=CROSS_ENCODER_PROVIDER, model_name="")


def test_build_reranker_cross_encoder_returns_configured_instance() -> None:
    reranker = build_reranker(provider_name=CROSS_ENCODER_PROVIDER, model_name="some/model", timeout_seconds=2.5)
    assert isinstance(reranker, CrossEncoderReranker)
    assert reranker.model_name == "some/model"
    assert reranker.timeout_seconds == 2.5


def test_build_reranker_rejects_unsupported_provider() -> None:
    with pytest.raises(RerankerError):
        build_reranker(provider_name="not_a_real_provider")


# --- rerank_candidates: fail-safe (production) vs fail-loud (evaluation) ---

def test_rerank_candidates_falls_back_to_dense_order_on_failure_by_default() -> None:
    candidates = [_match("a", score=0.9), _match("b", score=0.5)]
    reranker = _cross_encoder_with(FakeCrossEncoderModel(raise_error=RuntimeError("boom")))
    outcome = rerank_candidates(reranker, query="q", candidates=candidates, top_k=10, fail_loud=False)
    assert outcome.status == "failed"
    assert outcome.error_message is not None
    # Safe fallback reproduces unmodified dense ordering, exactly like NoOpReranker.
    assert [c.match.chunk_id for c in outcome.candidates] == ["a", "b"]
    assert all(c.rerank_score is None for c in outcome.candidates)


def test_rerank_candidates_fails_loud_for_evaluation() -> None:
    candidates = [_match("a", score=0.9)]
    reranker = _cross_encoder_with(FakeCrossEncoderModel(raise_error=RuntimeError("boom")))
    with pytest.raises(RerankerError):
        rerank_candidates(reranker, query="q", candidates=candidates, top_k=10, fail_loud=True)


def test_rerank_candidates_dense_rollback_via_no_op() -> None:
    # The one-line production rollback: passing NoOpReranker (RERANKER_PROVIDER=none)
    # reproduces the pre-reranking dense-ordered result exactly.
    candidates = [_match("a", score=0.9), _match("b", score=0.5), _match("c", score=0.2)]
    outcome = rerank_candidates(NoOpReranker(), query="q", candidates=candidates, top_k=10, fail_loud=False)
    assert [c.match.chunk_id for c in outcome.candidates] == ["a", "b", "c"]
    assert outcome.status == "no_reranker"


def test_rerank_candidates_success_path_reports_ok_metadata() -> None:
    candidates = [_match("a", score=0.5), _match("b", score=0.4)]
    model = FakeCrossEncoderModel(scores=[0.1, 0.9])
    reranker = _cross_encoder_with(model)
    outcome = rerank_candidates(reranker, query="q", candidates=candidates, top_k=10, fail_loud=False)
    assert outcome.status == "ok"
    assert outcome.provider_name == CROSS_ENCODER_PROVIDER
    assert outcome.model_name == "fake-cross-encoder"
    assert outcome.latency_ms >= 0


# --- isolation: reranking never introduces candidates outside the input set ---

def test_reranking_never_introduces_documents_outside_the_input_candidate_set() -> None:
    candidates = [_match("a", document_id="doc-1", score=0.5), _match("b", document_id="doc-2", score=0.4)]
    model = FakeCrossEncoderModel(scores=[0.9, 0.1])
    reranker = _cross_encoder_with(model)
    outcome = rerank_candidates(reranker, query="q", candidates=candidates, top_k=10, fail_loud=False)
    allowed_document_ids = {c.document_id for c in candidates}
    assert all(c.match.document_id in allowed_document_ids for c in outcome.candidates)
    assert len(outcome.candidates) == len(candidates)


def test_reranking_top_k_never_expands_candidate_count() -> None:
    candidates = [_match(str(i), score=1.0) for i in range(3)]
    model = FakeCrossEncoderModel(scores=[0.1, 0.2, 0.3])
    reranker = _cross_encoder_with(model)
    outcome = rerank_candidates(reranker, query="q", candidates=candidates, top_k=50, fail_loud=False)
    assert len(outcome.candidates) == len(candidates)
