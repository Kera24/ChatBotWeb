"""Unit tests for app.ai.guardrails.evidence_confidence (Retrieval & Answer
Pipeline V3 experiment, docs/future/RetrievalOptimisation.md Part 9) - the
deterministic, explainable Evidence Confidence model."""

from app.ai.guardrails.evidence_confidence import (
    ChunkEvidenceSignal,
    ConfidenceBand,
    compute_evidence_confidence,
)
from app.ai.guardrails.evidence_sufficiency import EvidenceSufficiencyVerdict, RequestedFact
from app.ai.guardrails.reason_codes import GuardrailReasonCode


def _verdict(sufficient: bool, reason_code: GuardrailReasonCode = GuardrailReasonCode.SUFFICIENT_EVIDENCE) -> EvidenceSufficiencyVerdict:
    return EvidenceSufficiencyVerdict(
        sufficient=sufficient, reason_code=reason_code,
        requested_fact=RequestedFact(entities=(), attribute_type=None, off_topic_likely=False),
        chunk_outcomes=("direct_support",) if sufficient else ("insufficient_evidence",),
    )


def test_insufficient_verdict_scores_zero_and_band_none() -> None:
    result = compute_evidence_confidence(verdict=_verdict(False, GuardrailReasonCode.REQUESTED_FACT_ABSENT), chunk_signals=())
    assert result.score == 0.0
    assert result.band == ConfidenceBand.NONE
    assert result.reason_codes == ("requested_fact_absent",)


def test_sufficient_with_no_supporting_chunks_is_a_pass_through_not_a_score() -> None:
    # The "no specific fact to verify" pass-through case (empty chunk_outcomes
    # upstream) - sufficient but nothing chunk-level to score.
    result = compute_evidence_confidence(verdict=_verdict(True), chunk_signals=())
    assert result.score == 0.0
    assert result.band == ConfidenceBand.NONE


def test_single_weak_signal_reaches_medium_not_high() -> None:
    signals = (ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=0.6),)
    result = compute_evidence_confidence(verdict=_verdict(True), chunk_signals=signals)
    assert result.band in (ConfidenceBand.LOW, ConfidenceBand.MEDIUM)
    assert result.band != ConfidenceBand.HIGH


def test_multiple_independent_signals_reach_high() -> None:
    signals = (
        ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=0.85, lexical_score=0.5, rerank_score=0.9, source_channels=("dense", "lexical"), cited=True),
        ChunkEvidenceSignal(chunk_id="c2", outcome="direct_support", dense_score=0.7),
    )
    result = compute_evidence_confidence(verdict=_verdict(True), chunk_signals=signals)
    assert result.band == ConfidenceBand.HIGH
    assert result.contributing_signals["supporting_chunk_count"] == 2
    assert result.contributing_signals["multi_chunk_agreement"] is True
    assert result.contributing_signals["lexical_corroborated"] is True


def test_non_supporting_chunks_are_ignored_in_scoring() -> None:
    signals = (
        ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=0.5),
        ChunkEvidenceSignal(chunk_id="c2", outcome="topic_match_only", dense_score=0.99),  # must not inflate the score
    )
    result = compute_evidence_confidence(verdict=_verdict(True), chunk_signals=signals)
    assert result.contributing_signals["supporting_chunk_count"] == 1


def test_score_is_bounded_and_deterministic() -> None:
    signals = (ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=1.0, lexical_score=1.0, rerank_score=1.0, source_channels=("dense", "lexical"), cited=True),)
    first = compute_evidence_confidence(verdict=_verdict(True), chunk_signals=signals)
    second = compute_evidence_confidence(verdict=_verdict(True), chunk_signals=signals)
    assert first == second
    assert 0.0 <= first.score <= 1.0


def test_out_of_range_rerank_score_is_clamped() -> None:
    # Cross-encoder logits are not guaranteed to be 0-1 - must never produce
    # an out-of-range confidence score.
    signals = (ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=0.5, rerank_score=15.0),)
    result = compute_evidence_confidence(verdict=_verdict(True), chunk_signals=signals)
    assert 0.0 <= result.score <= 1.0
