from __future__ import annotations

from dataclasses import replace

from app.access.messages.output.citations import rewrite_citation_markers, validate_and_project_citations
from app.access.messages.output.contracts import PublicOutputFormat, PublicOutputSanitisationRequest, PublicOutputSanitisationResult
from app.access.messages.output.leakage import detect_system_prompt_leakage, high_confidence_identifier_leakage, redact_internal_leakage
from app.access.messages.output.links import sanitise_links
from app.access.messages.output.markdown import enforce_answer_length, escape_public_text, html_to_text, normalise_markdown_text

SANITISER_DECISION_VERSION = "public-output-sanitiser-v1"
SAFE_FALLBACK_ANSWER = "The assistant could not provide a safe answer from the available knowledge. Please try rephrasing the question."


class PublicOutputSanitiser:
    def __init__(
        self,
        *,
        max_answer_characters: int = 4000,
        max_answer_bytes: int = 12000,
        max_paragraphs: int = 12,
        max_list_items: int = 20,
        max_links: int = 8,
        max_link_length: int = 512,
        max_inline_code_chars: int = 120,
        max_citations: int = 5,
    ) -> None:
        self.max_answer_characters = max_answer_characters
        self.max_answer_bytes = max_answer_bytes
        self.max_paragraphs = max_paragraphs
        self.max_list_items = max_list_items
        self.max_links = max_links
        self.max_link_length = max_link_length
        self.max_inline_code_chars = max_inline_code_chars
        self.max_citations = max_citations

    def sanitise(self, request: PublicOutputSanitisationRequest) -> PublicOutputSanitisationResult:
        categories: set[str] = set()
        raw_answer = request.answer or ""
        safe_citations, index_map, citation_result = validate_and_project_citations(request.authorised_citations, max_citations=self.max_citations)
        severe_leakage = detect_system_prompt_leakage(raw_answer)
        severe_internal = high_confidence_identifier_leakage(raw_answer, request.known_internal_values) and "Traceback" in raw_answer
        if severe_leakage or severe_internal:
            categories.add("system_prompt_leakage" if severe_leakage else "internal_leakage")
            return self._fallback_result(request, categories=categories, citation_result=replace(citation_result, valid_count=0, removed_count=citation_result.removed_count + len(safe_citations)))

        text, html_removed = html_to_text(raw_answer)
        if html_removed:
            categories.add("html")
        text, normalise_categories = normalise_markdown_text(
            text,
            max_paragraphs=self.max_paragraphs,
            max_list_items=self.max_list_items,
            max_inline_code_chars=self.max_inline_code_chars,
        )
        categories.update(normalise_categories)
        link_result = sanitise_links(text, max_links=self.max_links, max_url_length=self.max_link_length)
        text = link_result.text
        categories.update(link_result.categories)
        text, leakage_categories, leakage_detected = redact_internal_leakage(text, request.known_internal_values)
        categories.update(leakage_categories)
        text, marker_rewritten, markers_missing = rewrite_citation_markers(text, index_map)
        if marker_rewritten:
            categories.add("citation_marker")
        if markers_missing and request.answer_state == "answered":
            categories.add("citation_marker_missing")
        text, truncated = enforce_answer_length(text.strip(), max_chars=self.max_answer_characters, max_bytes=self.max_answer_bytes)
        if truncated:
            categories.add("truncated")
        text = escape_public_text(text)
        answer_state = _safe_answer_state(request.answer_state, fallback_used=request.fallback_used)
        if answer_state == "answered" and citation_result.valid_count == 0 and request.authorised_citations:
            answer_state = "low_confidence"
            categories.add("answer_state_downgraded")
        if markers_missing and answer_state == "answered":
            answer_state = "low_confidence"
            categories.add("answer_state_downgraded")
        if request.fallback_used or answer_state == "fallback":
            safe_citations = []
            citation_result = replace(citation_result, valid_count=0, removed_count=citation_result.removed_count + len(safe_citations))
        citation_result = replace(citation_result, marker_rewritten=marker_rewritten, required_citations_missing=markers_missing)
        return PublicOutputSanitisationResult(
            safe_answer=text or SAFE_FALLBACK_ANSWER,
            output_format=PublicOutputFormat.PLAIN_TEXT,
            answer_state=answer_state,
            safe_citations=safe_citations if answer_state != "fallback" else [],
            sanitisation_applied=bool(categories),
            removed_content_categories=tuple(sorted(categories)),
            leakage_detected=leakage_detected,
            citation_validation_result=citation_result,
            fallback_replaced=False,
            decision_version=SANITISER_DECISION_VERSION,
            safe_metadata={
                "removed_categories": tuple(sorted(categories)),
                "citation_count": len(safe_citations if answer_state != "fallback" else []),
                "sanitiser_version": SANITISER_DECISION_VERSION,
            },
        )

    def _fallback_result(self, request: PublicOutputSanitisationRequest, *, categories: set[str], citation_result) -> PublicOutputSanitisationResult:  # noqa: ANN001
        return PublicOutputSanitisationResult(
            safe_answer=SAFE_FALLBACK_ANSWER,
            output_format=PublicOutputFormat.PLAIN_TEXT,
            answer_state="fallback",
            safe_citations=[],
            sanitisation_applied=True,
            removed_content_categories=tuple(sorted(categories | {"fallback_replacement"})),
            leakage_detected=True,
            citation_validation_result=citation_result,
            fallback_replaced=True,
            decision_version=SANITISER_DECISION_VERSION,
            safe_metadata={"removed_categories": tuple(sorted(categories)), "citation_count": 0, "sanitiser_version": SANITISER_DECISION_VERSION},
        )


def _safe_answer_state(answer_state: str, *, fallback_used: bool) -> str:
    if fallback_used or answer_state == "fallback":
        return "fallback"
    if answer_state == "low_confidence":
        return "low_confidence"
    if answer_state == "answered":
        return "answered"
    return "fallback"