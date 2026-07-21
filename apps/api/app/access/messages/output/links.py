from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]\n]{0,200})\]\(([^)\s]{1,2048})\)")
_URL_RE = re.compile(r"(?i)\b(?:javascript|data|file|vbscript|blob|ftp):[^\s)]+|(?<!:)//[^\s)]+")


@dataclass(frozen=True)
class LinkSanitisationResult:
    text: str
    removed_count: int
    categories: tuple[str, ...]


def is_safe_public_url(url: str, *, max_length: int = 512) -> bool:
    if not url or len(url) > max_length:
        return False
    if _CONTROL_RE.search(url):
        return False
    stripped = url.strip()
    if stripped.startswith("//"):
        return False
    parsed = urlparse(stripped)
    if parsed.scheme.lower() != "https":
        return False
    if not parsed.netloc or "@" in parsed.netloc:
        return False
    return True


def sanitise_links(text: str, *, max_links: int = 8, max_url_length: int = 512) -> LinkSanitisationResult:
    removed = 0
    categories: set[str] = set()
    kept_links = 0

    def replace_markdown(match: re.Match[str]) -> str:
        nonlocal removed, kept_links
        label = match.group(1).strip() or "link"
        url = match.group(2).strip()
        if kept_links >= max_links or not is_safe_public_url(url, max_length=max_url_length):
            removed += 1
            categories.add("unsafe_link")
            return label
        kept_links += 1
        return f"{label} ({url})"

    text = _MARKDOWN_LINK_RE.sub(replace_markdown, text)

    def remove_unsafe_url(match: re.Match[str]) -> str:
        nonlocal removed
        removed += 1
        categories.add("unsafe_link")
        return "[removed link]"

    text = _URL_RE.sub(remove_unsafe_url, text)
    return LinkSanitisationResult(text=text, removed_count=removed, categories=tuple(sorted(categories)))