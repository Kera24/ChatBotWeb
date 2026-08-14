"""AnswerConstraints: Retrieval & Answer Pipeline V3 experiment
(docs/future/RetrievalOptimisation.md, Part 10) - a deterministic object
placed between evidence validation and generation that explicitly tells
generation "what is permitted by the retrieved evidence", and the
ANSWER/FALLBACK/CLARIFICATION_REQUIRED decision boundary (Part 12) that
produces it.

Built entirely from app.ai.guardrails.evidence_sufficiency's verdict and
app.ai.guardrails.evidence_confidence's score - NEVER from an LLM call. This
module contains no network I/O and no model inference; every field is a pure
function of already-computed guardrail data, so it is safe to run on every
request without adding provider latency or cost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.ai.guardrails.evidence_confidence import ChunkEvidenceSignal, EvidenceConfidence
from app.ai.guardrails.evidence_sufficiency import EvidenceSufficiencyVerdict
from app.ai.guardrails.reason_codes import GuardrailReasonCode

SAFE_MESSAGE_CLARIFICATION = (
    "The knowledge base has more than one answer that could apply here, depending on which plan, "
    "version, or scope you mean. Could you clarify which one you're asking about?"
)


class AnswerDecision(str, Enum):
    ANSWER = "answer"
    FALLBACK = "fallback"
    CLARIFICATION_REQUIRED = "clarification_required"


@dataclass(frozen=True)
class AnswerConstraints:
    decision: AnswerDecision
    answer_allowed: bool
    fallback_required: bool
    clarification_required: bool
    # Only these chunk ids may be used as authoritative context/citations for
    # generation (Part 11: "the model must never see rejected evidence as
    # authoritative context where avoidable") - empty whenever answer_allowed
    # is False.
    allowed_chunk_ids: tuple[str, ...]
    required_citation_chunk_ids: tuple[str, ...]
    conflicting_evidence: bool
    unsupported_requested_facts: tuple[str, ...]
    allowed_entities: tuple[str, ...]
    allowed_values: tuple[str, ...]
    safe_message: str | None
    reason_codes: tuple[str, ...]


# Narrow, reviewable vocabulary (not a broad keyword net) distinguishing a
# scope/plan-tier disambiguation question ("which plan do you mean?") from a
# genuine unresolved contradiction - reused from the same real-corpus
# evidence behind docs/adr/0034-promote-evidence-sufficiency-v2.md's
# conflicting-evidence false-positive analysis. Only used to choose between
# CLARIFICATION_REQUIRED and FALLBACK, both already-safe non-answering
# outcomes - never used to grant an answer.
_SCOPE_WORDS = re.compile(
    r"(?i)\b(starter|team|business|enterprise|standard|professional|monthly|annual|frankfurt|virginia)\b"
)


def _looks_like_scope_ambiguity(chunk_signals: tuple[ChunkEvidenceSignal, ...]) -> bool:
    supporting = [s for s in chunk_signals if s.outcome == "direct_support" and s.matched_value]
    supporting_values = {s.matched_value for s in supporting}
    if len(supporting_values) <= 1:
        return False
    # Content-grounded, not assumed: only classify as a real scope choice
    # (rather than an unresolved contradiction) when at least two of the
    # conflicting matches actually name a plan/tier/region/billing-cycle
    # word in their own matched sentence - i.e. there is a concrete "which
    # X do you mean?" to offer, not just "two different numbers turned up".
    scoped_matches = sum(1 for s in supporting if s.matched_sentence and _SCOPE_WORDS.search(s.matched_sentence))
    return scoped_matches >= 2


def decide_answer_outcome(
    *, verdict: EvidenceSufficiencyVerdict, confidence: EvidenceConfidence, chunk_signals: tuple[ChunkEvidenceSignal, ...] = ()
) -> AnswerDecision:
    """The core deterministic decision boundary (Part 12). Fallback triggers
    on the guardrail's own rejection (required fact absent, evidence
    confidence structurally absent, evidence constraints prohibit
    answering) - never on a model-reported confidence value, since no model
    has been called yet at this point in the pipeline.

    A CONFLICTING_EVIDENCE verdict splits two ways, per this task's own
    distinction between "unresolved genuine contradiction" (FALLBACK - don't
    guess) and "which plan/version/product do you mean?" (CLARIFICATION_REQUIRED
    - a real, answerable-once-disambiguated question): >=2 distinct
    candidate values means the user has a real choice to be offered;
    otherwise there is nothing concrete to ask them to choose between, so it
    stays a plain fallback."""
    if verdict.sufficient:
        # band == NONE with sufficient=True only occurs on the "no specific
        # fact to verify" pass-through (empty chunk_outcomes) - nothing to
        # fact-check, so this is a legitimate ANSWER, not a low-confidence
        # fallback (see evidence_confidence.py's own docstring for this
        # exact case).
        return AnswerDecision.ANSWER

    if verdict.reason_code == GuardrailReasonCode.CONFLICTING_EVIDENCE and _looks_like_scope_ambiguity(chunk_signals):
        return AnswerDecision.CLARIFICATION_REQUIRED

    return AnswerDecision.FALLBACK


def build_answer_constraints(
    *, verdict: EvidenceSufficiencyVerdict, confidence: EvidenceConfidence, chunk_signals: tuple[ChunkEvidenceSignal, ...]
) -> AnswerConstraints:
    decision = decide_answer_outcome(verdict=verdict, confidence=confidence, chunk_signals=chunk_signals)
    answer_allowed = decision == AnswerDecision.ANSWER

    supporting = tuple(s for s in chunk_signals if s.outcome == "direct_support")
    allowed_chunk_ids = tuple(s.chunk_id for s in supporting) if answer_allowed else ()
    allowed_values = tuple(dict.fromkeys(s.matched_value for s in supporting if s.matched_value)) if answer_allowed else ()

    conflicting_evidence = verdict.reason_code == GuardrailReasonCode.CONFLICTING_EVIDENCE
    unsupported_requested_facts = () if answer_allowed else tuple(verdict.requested_fact.entities)

    reason_codes = list(confidence.reason_codes)
    if decision == AnswerDecision.CLARIFICATION_REQUIRED:
        reason_codes.append(GuardrailReasonCode.AMBIGUOUS_REQUEST.value)

    safe_message = None
    if decision == AnswerDecision.FALLBACK:
        safe_message = verdict.safe_message
    elif decision == AnswerDecision.CLARIFICATION_REQUIRED:
        safe_message = SAFE_MESSAGE_CLARIFICATION

    return AnswerConstraints(
        decision=decision,
        answer_allowed=answer_allowed,
        fallback_required=decision == AnswerDecision.FALLBACK,
        clarification_required=decision == AnswerDecision.CLARIFICATION_REQUIRED,
        allowed_chunk_ids=allowed_chunk_ids,
        required_citation_chunk_ids=allowed_chunk_ids,
        conflicting_evidence=conflicting_evidence,
        unsupported_requested_facts=unsupported_requested_facts,
        allowed_entities=tuple(verdict.requested_fact.entities) if answer_allowed else (),
        allowed_values=allowed_values,
        safe_message=safe_message,
        reason_codes=tuple(reason_codes),
    )
