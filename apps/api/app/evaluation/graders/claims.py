"""Deterministic, heuristic claim-level splitting (Section 4). Splits an
answer into sentence-level claims and associates each with the citation
markers ("[1]", "[2]") that appear in or immediately after it, so
claim-to-evidence support can be checked per claim rather than only for the
answer as a whole.

Explicitly not a claim of perfect claim extraction (Section 4's own
instruction) - a sentence is not always exactly one factual claim, and a
citation marker's scope (which preceding clause it actually supports) is
ambiguous in natural prose. This is a best-effort structural aid for the
grader and for deterministic numeric/date/currency checks, not a substitute
for the deterministic value-type checks already implemented in
app.ai.guardrails.evidence_sufficiency, which remain authoritative for
launch-critical grounding decisions - this module is evaluation/grading
tooling only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.guardrails.evidence_sufficiency import ExpectedValueType, extract_values

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CITATION_MARKER = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class ExtractedClaim:
    text: str
    cited_evidence_ids: tuple[str, ...]
    numeric_values: tuple[str, ...]
    currency_values: tuple[str, ...]
    date_values: tuple[str, ...]
    duration_values: tuple[str, ...]


def extract_claims(answer: str) -> tuple[ExtractedClaim, ...]:
    claims = []
    for sentence in _SENTENCE_SPLIT.split(answer.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        citation_ids = tuple(_CITATION_MARKER.findall(sentence))
        claims.append(ExtractedClaim(
            text=sentence,
            cited_evidence_ids=citation_ids,
            numeric_values=tuple(extract_values(sentence, ExpectedValueType.NUMERIC)),
            currency_values=tuple(extract_values(sentence, ExpectedValueType.CURRENCY)),
            date_values=tuple(extract_values(sentence, ExpectedValueType.DATE)),
            duration_values=tuple(extract_values(sentence, ExpectedValueType.DURATION)),
        ))
    return tuple(claims)


def deterministic_value_support(claim: ExtractedClaim, evidence_text: str) -> bool | None:
    """Authoritative, deterministic check (reusing the same value extractors
    already validated for the evidence-sufficiency guardrail): does the
    evidence contain every numeric/currency/date/duration value the claim
    states? Returns None when the claim has no checkable values (a grader's
    judgement is then the only signal for that claim) - this deterministic
    check, when it does apply, is authoritative and is never overridden by a
    grader's own opinion (Section 4's "preserve deterministic checks as
    authoritative")."""
    values = claim.numeric_values + claim.currency_values + claim.date_values + claim.duration_values
    if not values:
        return None
    lowered = evidence_text.lower()
    return all(value.lower() in lowered for value in values)
