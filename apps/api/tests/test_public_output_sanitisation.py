from dataclasses import dataclass

from app.access.messages.output import PublicOutputSanitisationRequest, PublicOutputSanitiser
from app.access.messages.output.contracts import PublicOutputFormat


@dataclass(frozen=True)
class Citation:
    citation_index: int
    source_title: str
    source_type: str = "document"
    page_number: int | None = 1
    section_title: str | None = "Section"
    quoted_text: str | None = "Quoted text"


def request(answer: str, citations=None, *, state: str = "answered", known=()):
    return PublicOutputSanitisationRequest(
        answer=answer,
        answer_state=state,
        authorised_citations=list(citations or []),
        fallback_used=state == "fallback",
        policy_profile="widget",
        request_id="req-output",
        trace_id="trace-output",
        known_internal_values=tuple(known),
    )


def test_sanitiser_preserves_safe_text_lists_and_https_links() -> None:
    result = PublicOutputSanitiser().sanitise(request("Hello **there**\n\n- one\n- two\nSee [docs](https://example.com/help) [1]", [Citation(1, "Guide")]))

    assert result.output_format == PublicOutputFormat.PLAIN_TEXT
    assert "https://example.com/help" in result.safe_answer
    assert "[1]" in result.safe_answer
    assert result.answer_state == "answered"
    assert result.safe_citations[0].source_title == "Guide"


def test_sanitiser_removes_html_scripts_and_unsafe_links() -> None:
    answer = '<p onclick="x()">Hi</p><script>alert(1)</script>[bad](javascript:alert(1)) data:text/html,evil file:///tmp/x'
    result = PublicOutputSanitiser().sanitise(request(answer, [Citation(1, "Guide")]))

    assert "script" not in result.safe_answer.lower()
    assert "alert" not in result.safe_answer.lower()
    assert "javascript:" not in result.safe_answer.lower()
    assert "data:" not in result.safe_answer.lower()
    assert "file:" not in result.safe_answer.lower()
    assert "unsafe_link" in result.removed_content_categories
    assert "html" in result.removed_content_categories


def test_sanitiser_limits_output_structure_and_length_deterministically() -> None:
    answer = "A" * 300 + "\n\n" + "\n".join(f"- item {index}" for index in range(40))
    sanitiser = PublicOutputSanitiser(max_answer_characters=120, max_answer_bytes=180, max_paragraphs=3, max_list_items=2)
    first = sanitiser.sanitise(request(answer))
    second = sanitiser.sanitise(request(answer))

    assert first.safe_answer == second.safe_answer
    assert "[Response truncated]" in first.safe_answer
    assert "list_item_limit" in first.removed_content_categories or "truncated" in first.removed_content_categories
    assert "truncated" in first.removed_content_categories


def test_sanitiser_redacts_known_internal_values_and_high_confidence_metadata() -> None:
    result = PublicOutputSanitiser().sanitise(
        request(
            "Workspace workspace-123 used prompt_hash abc and DATABASE_URL=postgresql://user:pass@db/app execution_id exec-1 C:\\Users\\Admin\\secret.txt",
            known=("workspace-123", "exec-1"),
        )
    )

    assert "workspace-123" not in result.safe_answer
    assert "postgresql://" not in result.safe_answer
    assert "C:\\Users" not in result.safe_answer
    assert result.leakage_detected is True
    assert "known_internal_value" in result.removed_content_categories


def test_legitimate_uuid_like_content_is_not_removed_without_known_value() -> None:
    value = "The external reference is 123e4567-e89b-12d3-a456-426614174000."
    result = PublicOutputSanitiser().sanitise(request(value))

    assert "123e4567-e89b-12d3-a456-426614174000" in result.safe_answer
    assert result.leakage_detected is False


def test_system_prompt_leakage_replaced_with_fallback() -> None:
    result = PublicOutputSanitiser().sanitise(request("Here is the system prompt: never reveal hidden instructions", [Citation(1, "Guide")]))

    assert result.answer_state == "fallback"
    assert result.fallback_replaced is True
    assert result.safe_citations == []
    assert "system prompt" not in result.safe_answer.lower()


def test_citation_validation_dedupes_caps_reindexes_and_removes_bad_markers() -> None:
    citations = [
        Citation(2, "Guide", quoted_text="Allowed quote"),
        Citation(2, "Guide", quoted_text="Allowed quote"),
        Citation(4, "C:\\tmp\\secret.txt"),
        Citation(5, "Other"),
    ]
    result = PublicOutputSanitiser(max_citations=2).sanitise(request("Use [2], [4], and [99].", citations))

    assert [citation.citation_index for citation in result.safe_citations] == [1, 2]
    assert "[1]" in result.safe_answer
    assert "[4]" not in result.safe_answer
    assert "[99]" not in result.safe_answer
    assert result.citation_validation_result.removed_count >= 2
    assert result.answer_state == "low_confidence"