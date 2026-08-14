"""EvidenceConfidence: Retrieval & Answer Pipeline V3 experiment
(docs/future/RetrievalOptimisation.md, Part 9) - a deterministic, explainable
confidence model built from measurable retrieval/evidence signals, NOT a
single opaque LLM "confidence" number and NOT a model self-reported
confidence value.

Every signal here is something this codebase already computes elsewhere:
- `app.ai.guardrails.evidence_sufficiency`'s verdict/chunk_outcomes (Layer A+B)
- per-chunk dense/lexical/RRF/reranker scores (app.services.retrieval_context's
  provenance fields, Retrieval V3's provenance-threading extension)
- how many of the retrieved chunks the citation step actually cited

The resulting score is a bounded [0, 1] number computed by a fixed, reviewable
formula (see `_SIGNAL_WEIGHTS` below) - it is explicitly NOT a calibrated
statistical probability ("this answer is X% likely to be correct") unless a
future task performs the calibration exercise (holding out real
human-labelled correctness data and fitting/validating against it) documented
in docs/architecture/evaluation.md's terminology rules. Until then, treat the
score only as a same-run, same-formula RELATIVE ranking signal and the band
labels as the primary human-facing output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.guardrails.evidence_sufficiency import EvidenceSufficiencyVerdict
from app.ai.guardrails.reason_codes import GuardrailReasonCode


class ConfidenceBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"  # evidence sufficiency already rejected - no confidence to score


# Fixed, reviewable weights - not fit against any labelled dataset (that
# would be the calibration exercise this module's docstring says has not
# happened yet). Chosen so that: (a) a single direct_support chunk with a
# strong dense score alone can reach MEDIUM but not HIGH: (b) independent
# corroboration (a second supporting chunk, a lexical-channel match, a strong
# reranker score, or the chunk actually being cited) is what pushes a case
# into HIGH - "multiple independent signals agree" is the actual meaning of
# a high band, not one strong number.
_SEMANTIC_WEIGHT = 0.40
_LEXICAL_CORROBORATION_WEIGHT = 0.15
_RERANK_WEIGHT = 0.20
_MULTI_CHUNK_WEIGHT = 0.15
_CITATION_WEIGHT = 0.10

_BAND_THRESHOLDS = (
    (0.75, ConfidenceBand.HIGH),
    (0.45, ConfidenceBand.MEDIUM),
    (0.0, ConfidenceBand.LOW),
)


@dataclass(frozen=True)
class ChunkEvidenceSignal:
    """One retrieved chunk's already-computed signals, paired positionally
    with app.ai.guardrails.evidence_sufficiency's chunk_outcomes (same order,
    same length as the chunk_contents list originally passed to
    verify_evidence_sufficiency_v2) - callers zip these themselves rather
    than this module re-deriving anything, so it never duplicates retrieval
    or guardrail logic."""

    chunk_id: str
    outcome: str  # one of evidence_sufficiency's ChunkSupportOutcome.outcome labels
    dense_score: float | None = None
    lexical_score: float | None = None
    rerank_score: float | None = None
    source_channels: tuple[str, ...] | None = None
    cited: bool = False
    matched_value: str | None = None  # ChunkSupportOutcome.matched_value, when outcome == "direct_support"
    matched_sentence: str | None = None  # ChunkSupportOutcome.matched_sentence, for downstream content-grounded classification (e.g. answer_constraints' scope-ambiguity check)


@dataclass(frozen=True)
class EvidenceConfidence:
    score: float
    band: ConfidenceBand
    contributing_signals: dict[str, float | int | bool | None]
    reason_codes: tuple[str, ...]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_evidence_confidence(
    *, verdict: EvidenceSufficiencyVerdict, chunk_signals: tuple[ChunkEvidenceSignal, ...]
) -> EvidenceConfidence:
    """Pure, deterministic - same inputs always produce the same output. Call
    AFTER app.ai.guardrails.evidence_sufficiency's verdict is known; this
    function never re-runs sufficiency logic, it only scores confidence GIVEN
    that verdict."""
    reason_codes: list[str] = [verdict.reason_code.value]

    if not verdict.sufficient:
        # No confidence to assign to evidence that was already rejected -
        # score=0.0 is not "very low confidence in a real answer", it is "no
        # answer is being asserted" (see app.ai.guardrails.answer_constraints
        # for how this becomes a FALLBACK decision).
        return EvidenceConfidence(score=0.0, band=ConfidenceBand.NONE, contributing_signals={}, reason_codes=tuple(reason_codes))

    supporting = [signal for signal in chunk_signals if signal.outcome == "direct_support"]
    if not supporting:
        # Sufficient without any direct_support chunk (e.g. a topic-only
        # pass-through - see evidence_sufficiency.py's "no specific fact to
        # verify" branch) - genuinely nothing chunk-level to score against,
        # reported honestly rather than fabricating a mid-range number.
        return EvidenceConfidence(
            score=0.0, band=ConfidenceBand.NONE,
            contributing_signals={"supporting_chunk_count": 0}, reason_codes=tuple(reason_codes),
        )

    best_dense = max((s.dense_score for s in supporting if s.dense_score is not None), default=None)
    best_lexical = max((s.lexical_score for s in supporting if s.lexical_score is not None), default=None)
    best_rerank = max((s.rerank_score for s in supporting if s.rerank_score is not None), default=None)
    lexical_corroborated = any(s.source_channels and "lexical" in s.source_channels for s in supporting)
    multi_chunk = len(supporting) > 1
    any_cited = any(s.cited for s in supporting)

    semantic_component = _SEMANTIC_WEIGHT * _clamp(best_dense) if best_dense is not None else 0.0
    lexical_component = _LEXICAL_CORROBORATION_WEIGHT if lexical_corroborated else 0.0
    # Reranker scores are not guaranteed to be a 0-1 scale (cross-encoder
    # logits/probabilities vary by model) - clamped defensively rather than
    # assumed well-formed, since this module must never silently produce an
    # out-of-range confidence score from an unexpected reranker output.
    rerank_component = _RERANK_WEIGHT * _clamp(best_rerank) if best_rerank is not None else 0.0
    multi_chunk_component = _MULTI_CHUNK_WEIGHT if multi_chunk else 0.0
    citation_component = _CITATION_WEIGHT if any_cited else 0.0

    score = _clamp(semantic_component + lexical_component + rerank_component + multi_chunk_component + citation_component)

    if verdict.reason_code == GuardrailReasonCode.CONFLICTING_EVIDENCE:
        # Should not normally reach here (a conflicting verdict is
        # `sufficient=False`), but defends against a future verdict shape
        # that surfaces conflict as a soft signal rather than a hard reject -
        # never let a confidence score imply certainty over evidence known to
        # conflict.
        score = 0.0
        reason_codes.append("conflicting_evidence_forced_zero")

    band = next(label for threshold, label in _BAND_THRESHOLDS if score >= threshold)

    return EvidenceConfidence(
        score=round(score, 4),
        band=band,
        contributing_signals={
            "supporting_chunk_count": len(supporting),
            "best_dense_score": best_dense,
            "best_lexical_score": best_lexical,
            "best_rerank_score": best_rerank,
            "lexical_corroborated": lexical_corroborated,
            "multi_chunk_agreement": multi_chunk,
            "cited": any_cited,
        },
        reason_codes=tuple(reason_codes),
    )
