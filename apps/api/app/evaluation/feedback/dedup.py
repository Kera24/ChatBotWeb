"""Deterministic candidate deduplication.

Semantic (embedding-based) similarity is explicitly out of scope for this
iteration - see docs/03_AI/Continuous_Evaluation_Architecture.md. Duplicate
suggestions here are always deterministic (hash + token overlap) and are never
auto-merged; a reviewer decides in the triage UI.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationCandidate

_WHITESPACE_PATTERN = re.compile(r"\s+")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")

# Below this token-overlap ratio, two candidates are not surfaced as possible
# duplicates - low enough to catch paraphrases, high enough to avoid flooding
# reviewers with unrelated questions that happen to share common words.
JACCARD_DUPLICATE_THRESHOLD = 0.6


def normalize_question(question: str) -> str:
    lowered = question.strip().lower()
    stripped = _PUNCTUATION_PATTERN.sub("", lowered)
    return _WHITESPACE_PATTERN.sub(" ", stripped).strip()


def compute_dedup_hash(question: str, *, widget_id: str, reason_code: str) -> str:
    normalized = normalize_question(question)
    payload = f"{widget_id}|{reason_code}|{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _token_set(question: str) -> set[str]:
    return set(normalize_question(question).split())


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    return intersection / union if union else 0.0


@dataclass(frozen=True)
class DuplicateSuggestion:
    candidate: EvaluationCandidate
    match_reason: str
    similarity: float


def find_potential_duplicates(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    question: str,
    dedup_hash: str,
    exclude_candidate_id: str | None = None,
) -> list[DuplicateSuggestion]:
    """Deterministic-only duplicate suggestions among *open* (non-terminal)
    candidates for the same assistant. Never auto-merges."""
    statement = select(EvaluationCandidate).where(
        EvaluationCandidate.organisation_id == organisation_id,
        EvaluationCandidate.workspace_id == workspace_id,
        EvaluationCandidate.widget_id == widget_id,
        EvaluationCandidate.triage_status.notin_(("rejected", "duplicate", "resolved")),
    )
    if exclude_candidate_id is not None:
        statement = statement.where(EvaluationCandidate.id != exclude_candidate_id)
    candidates = list(db.execute(statement).scalars().all())

    question_tokens = _token_set(question)
    suggestions: list[DuplicateSuggestion] = []
    for other in candidates:
        if other.dedup_hash == dedup_hash:
            suggestions.append(DuplicateSuggestion(candidate=other, match_reason="dedup_hash", similarity=1.0))
            continue
        other_question = other.redacted_question or ""
        similarity = _jaccard_similarity(question_tokens, _token_set(other_question))
        if similarity >= JACCARD_DUPLICATE_THRESHOLD:
            suggestions.append(DuplicateSuggestion(candidate=other, match_reason="token_overlap", similarity=similarity))
    suggestions.sort(key=lambda item: item.similarity, reverse=True)
    return suggestions
