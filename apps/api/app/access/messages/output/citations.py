from __future__ import annotations

import re
from typing import Any

from app.access.messages.output.contracts import CitationValidationResult, PublicOutputCitation
from app.access.messages.output.markdown import html_to_text

_MARKER_RE = re.compile(r"\[(\d{1,3})\]")
_PATH_RE = re.compile(r"(?i)(?:[a-z]:\\|/var/|/tmp/|/home/|s3://|gs://|blob:|file:)")


def validate_and_project_citations(citations: list[Any], *, max_citations: int = 5, max_title_chars: int = 200, max_type_chars: int = 80, max_section_chars: int = 200, max_quote_chars: int = 500) -> tuple[list[PublicOutputCitation], dict[int, int], CitationValidationResult]:
    seen: set[tuple[object, ...]] = set()
    projected: list[PublicOutputCitation] = []
    index_map: dict[int, int] = {}
    removed = 0
    for citation in sorted(citations, key=lambda item: int(getattr(item, "citation_index", 0) or 0)):
        original_index = int(getattr(citation, "citation_index", 0) or 0)
        if original_index <= 0:
            removed += 1
            continue
        title = _clean_field(getattr(citation, "source_title", None), max_title_chars)
        source_type = _clean_field(getattr(citation, "source_type", None), max_type_chars)
        if not title or not source_type or _unsafe_reference(title) or _unsafe_reference(source_type):
            removed += 1
            continue
        section = _clean_field(getattr(citation, "section_title", None), max_section_chars) or None
        quote = _clean_field(getattr(citation, "quoted_text", None), max_quote_chars) or None
        if (section and _unsafe_reference(section)) or (quote and _unsafe_reference(quote)):
            removed += 1
            continue
        page_number = getattr(citation, "page_number", None)
        if page_number is not None:
            try:
                page_number = max(1, min(int(page_number), 100000))
            except (TypeError, ValueError):
                page_number = None
        key = (title, source_type, page_number, section, quote)
        if key in seen:
            removed += 1
            if original_index not in index_map:
                index_map[original_index] = next((item.citation_index for item in projected if (item.source_title, item.source_type, item.page_number, item.section_title, item.quoted_text) == key), 0)
            continue
        if len(projected) >= max_citations:
            removed += 1
            continue
        seen.add(key)
        new_index = len(projected) + 1
        index_map[original_index] = new_index
        projected.append(
            PublicOutputCitation(
                citation_index=new_index,
                source_title=title,
                source_type=source_type,
                page_number=page_number,
                section_title=section,
                quoted_text=quote,
            )
        )
    return projected, index_map, CitationValidationResult(valid_count=len(projected), removed_count=removed)


def rewrite_citation_markers(answer: str, index_map: dict[int, int]) -> tuple[str, bool, bool]:
    rewritten = False
    missing = False

    def replace(match: re.Match[str]) -> str:
        nonlocal rewritten, missing
        original = int(match.group(1))
        replacement = index_map.get(original)
        if replacement is None or replacement <= 0:
            rewritten = True
            missing = True
            return ""
        if replacement != original:
            rewritten = True
        return f"[{replacement}]"

    return _MARKER_RE.sub(replace, answer), rewritten, missing


def _clean_field(value: object, max_chars: int) -> str:
    if value is None:
        return ""
    text, _ = html_to_text(str(value).replace("\x00", ""))
    text = " ".join(text.split())
    return text[:max_chars]


def _unsafe_reference(value: str) -> bool:
    return bool(_PATH_RE.search(value))