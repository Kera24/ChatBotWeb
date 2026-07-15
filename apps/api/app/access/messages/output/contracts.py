from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class PublicOutputFormat(StrEnum):
    PLAIN_TEXT = "plain_text"
    RESTRICTED_MARKDOWN = "restricted_markdown"


@dataclass(frozen=True)
class PublicOutputCitation:
    citation_index: int
    source_title: str
    source_type: str
    page_number: int | None = None
    section_title: str | None = None
    quoted_text: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class CitationValidationResult:
    valid_count: int
    removed_count: int
    marker_rewritten: bool = False
    required_citations_missing: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PublicOutputSanitisationRequest:
    answer: str
    answer_state: str
    authorised_citations: list[Any]
    fallback_used: bool
    policy_profile: str
    request_id: str
    trace_id: str
    known_internal_values: tuple[str, ...] = ()
    internal_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublicOutputSanitisationResult:
    safe_answer: str
    output_format: PublicOutputFormat
    answer_state: str
    safe_citations: list[PublicOutputCitation]
    sanitisation_applied: bool
    removed_content_categories: tuple[str, ...]
    leakage_detected: bool
    citation_validation_result: CitationValidationResult
    fallback_replaced: bool
    decision_version: str
    safe_metadata: dict[str, object] = field(default_factory=dict)

    def public_payload(self) -> dict[str, object]:
        return {
            "answer": self.safe_answer,
            "answer_state": self.answer_state,
            "citations": [citation.to_dict() for citation in self.safe_citations],
            "fallback_used": self.fallback_replaced or self.answer_state == "fallback",
        }