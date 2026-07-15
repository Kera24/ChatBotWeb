from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INLINE_CODE_RE = re.compile(r"`([^`]{121,})`")
_LIST_ITEM_RE = re.compile(r"(?m)^\s*(?:[-*+] |\d+[.)] )")
_TRUNCATION = "\n\n[Response truncated]"


class _TextOnlyHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.removed = False
        self._blocked_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        self.removed = True
        if tag.lower() in {"script", "style", "iframe", "object", "embed", "svg", "math"}:
            self._blocked_depth += 1
        elif tag.lower() in {"br", "p", "div", "li"} and self._blocked_depth == 0:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        self.removed = True
        if tag.lower() in {"script", "style", "iframe", "object", "embed", "svg", "math"} and self._blocked_depth:
            self._blocked_depth -= 1
        elif tag.lower() in {"p", "div", "li"} and self._blocked_depth == 0:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._blocked_depth == 0:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._blocked_depth == 0:
            self.parts.append(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if self._blocked_depth == 0:
            self.parts.append(html.unescape(f"&#{name};"))


def html_to_text(value: str) -> tuple[str, bool]:
    parser = _TextOnlyHTMLParser()
    parser.feed(value)
    parser.close()
    text = "".join(parser.parts)
    return html.unescape(text), parser.removed


def escape_public_text(value: str) -> str:
    return html.escape(value, quote=False)


def normalise_markdown_text(value: str, *, max_paragraphs: int, max_list_items: int, max_inline_code_chars: int) -> tuple[str, tuple[str, ...]]:
    categories: set[str] = set()
    text = value.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text, control_count = _CONTROL_RE.subn("", text)
    if control_count:
        categories.add("control_character")
    text, code_count = _INLINE_CODE_RE.subn(lambda match: "`" + match.group(1)[:max_inline_code_chars] + "...`", text)
    if code_count:
        categories.add("inline_code_truncated")
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
    if len(paragraphs) > max_paragraphs:
        paragraphs = paragraphs[:max_paragraphs]
        categories.add("paragraph_limit")
    text = "\n\n".join(paragraphs) if paragraphs else text.strip()
    list_items = list(_LIST_ITEM_RE.finditer(text))
    if len(list_items) > max_list_items:
        cutoff = list_items[max_list_items].start()
        text = text[:cutoff].rstrip()
        categories.add("list_item_limit")
    return text, tuple(sorted(categories))


def enforce_answer_length(value: str, *, max_chars: int, max_bytes: int) -> tuple[str, bool]:
    text = value
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
        truncated = True
    while len(text.encode("utf-8")) > max_bytes and text:
        text = text[:-1].rstrip()
        truncated = True
    if truncated:
        suffix = _TRUNCATION
        while len((text + suffix).encode("utf-8")) > max_bytes and text:
            text = text[:-1].rstrip()
        text = text + suffix
    return text, truncated