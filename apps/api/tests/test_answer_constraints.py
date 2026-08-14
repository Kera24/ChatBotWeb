"""Unit tests for app.ai.guardrails.answer_constraints (Retrieval & Answer
Pipeline V3 experiment, docs/future/RetrievalOptimisation.md Part 10/12) -
AnswerConstraints and the ANSWER/FALLBACK/CLARIFICATION_REQUIRED decision
boundary."""

from app.ai.guardrails.answer_constraints import AnswerDecision, build_answer_constraints, decide_answer_outcome
from app.ai.guardrails.evidence_confidence import ChunkEvidenceSignal, compute_evidence_confidence
from app.ai.guardrails.evidence_sufficiency import EvidenceSufficiencyVerdict, RequestedFact
from app.ai.guardrails.reason_codes import GuardrailReasonCode


def _sufficient_verdict() -> EvidenceSufficiencyVerdict:
    return EvidenceSufficiencyVerdict(
        sufficient=True, reason_code=GuardrailReasonCode.SUFFICIENT_EVIDENCE,
        requested_fact=RequestedFact(entities=("Team",), attribute_type=None, off_topic_likely=False),
        chunk_outcomes=("direct_support",),
    )


def _absent_verdict() -> EvidenceSufficiencyVerdict:
    return EvidenceSufficiencyVerdict(
        sufficient=False, reason_code=GuardrailReasonCode.REQUESTED_FACT_ABSENT,
        requested_fact=RequestedFact(entities=("Foo",), attribute_type=None, off_topic_likely=False),
        chunk_outcomes=("insufficient_evidence",),
    )


def _conflicting_verdict() -> EvidenceSufficiencyVerdict:
    return EvidenceSufficiencyVerdict(
        sufficient=False, reason_code=GuardrailReasonCode.CONFLICTING_EVIDENCE,
        requested_fact=RequestedFact(entities=(), attribute_type=None, off_topic_likely=False),
        chunk_outcomes=("direct_support", "direct_support"),
    )


def test_sufficient_evidence_decides_answer() -> None:
    verdict = _sufficient_verdict()
    signals = (ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=0.7, cited=True),)
    confidence = compute_evidence_confidence(verdict=verdict, chunk_signals=signals)
    constraints = build_answer_constraints(verdict=verdict, confidence=confidence, chunk_signals=signals)
    assert constraints.decision == AnswerDecision.ANSWER
    assert constraints.answer_allowed is True
    assert constraints.fallback_required is False
    assert constraints.allowed_chunk_ids == ("c1",)
    assert constraints.required_citation_chunk_ids == ("c1",)


def test_requested_fact_absent_decides_fallback() -> None:
    verdict = _absent_verdict()
    confidence = compute_evidence_confidence(verdict=verdict, chunk_signals=())
    constraints = build_answer_constraints(verdict=verdict, confidence=confidence, chunk_signals=())
    assert constraints.decision == AnswerDecision.FALLBACK
    assert constraints.answer_allowed is False
    assert constraints.allowed_chunk_ids == ()
    assert constraints.unsupported_requested_facts == ("Foo",)


def test_scope_ambiguous_conflict_decides_clarification_required() -> None:
    verdict = _conflicting_verdict()
    signals = (
        ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", matched_value="$19", matched_sentence="The Starter plan costs $19 per month."),
        ChunkEvidenceSignal(chunk_id="c2", outcome="direct_support", matched_value="$79", matched_sentence="The Team plan costs $79 per month."),
    )
    confidence = compute_evidence_confidence(verdict=verdict, chunk_signals=signals)
    constraints = build_answer_constraints(verdict=verdict, confidence=confidence, chunk_signals=signals)
    assert constraints.decision == AnswerDecision.CLARIFICATION_REQUIRED
    assert constraints.clarification_required is True
    assert constraints.answer_allowed is False
    assert "which" in (constraints.safe_message or "").lower()


def test_genuine_contradiction_without_scope_words_decides_fallback_not_clarification() -> None:
    verdict = _conflicting_verdict()
    signals = (
        ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", matched_value="90 days", matched_sentence="Data is retained for 90 days."),
        ChunkEvidenceSignal(chunk_id="c2", outcome="direct_support", matched_value="60 days", matched_sentence="Data is retained for 60 days."),
    )
    confidence = compute_evidence_confidence(verdict=verdict, chunk_signals=signals)
    constraints = build_answer_constraints(verdict=verdict, confidence=confidence, chunk_signals=signals)
    assert constraints.decision == AnswerDecision.FALLBACK
    assert constraints.conflicting_evidence is True


def test_decision_never_answers_on_insufficient_evidence_regardless_of_confidence_inputs() -> None:
    # "Do not fallback merely because the model claims low confidence" cuts
    # both ways - the converse must also hold: no confidence signal can turn
    # an insufficient verdict into an answer.
    verdict = _absent_verdict()
    signals = (ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=1.0, rerank_score=1.0, cited=True),)
    confidence = compute_evidence_confidence(verdict=verdict, chunk_signals=signals)
    decision = decide_answer_outcome(verdict=verdict, confidence=confidence, chunk_signals=signals)
    assert decision == AnswerDecision.FALLBACK


def test_rejected_evidence_never_becomes_allowed_context() -> None:
    verdict = _sufficient_verdict()
    signals = (
        ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=0.7),
        ChunkEvidenceSignal(chunk_id="c2", outcome="topic_match_only", dense_score=0.9),
        ChunkEvidenceSignal(chunk_id="c3", outcome="insufficient_evidence"),
    )
    confidence = compute_evidence_confidence(verdict=verdict, chunk_signals=signals)
    constraints = build_answer_constraints(verdict=verdict, confidence=confidence, chunk_signals=signals)
    assert constraints.allowed_chunk_ids == ("c1",)
    assert "c2" not in constraints.allowed_chunk_ids
    assert "c3" not in constraints.allowed_chunk_ids


def test_constraints_are_deterministic() -> None:
    verdict = _sufficient_verdict()
    signals = (ChunkEvidenceSignal(chunk_id="c1", outcome="direct_support", dense_score=0.7),)
    confidence = compute_evidence_confidence(verdict=verdict, chunk_signals=signals)
    first = build_answer_constraints(verdict=verdict, confidence=confidence, chunk_signals=signals)
    second = build_answer_constraints(verdict=verdict, confidence=confidence, chunk_signals=signals)
    assert first == second
