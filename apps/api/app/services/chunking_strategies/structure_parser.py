"""Plain-text structural block parser.

Infers document structure - headings, paragraphs, lists, fenced code blocks,
pipe-delimited table rows - from the *plain text* the existing extraction
pipeline (`app.services.text_extraction`) produces. This module never
touches extraction and never invents structure extraction doesn't expose:
PDF/DOCX extraction in this pipeline discards layout information (font
size, bold, indentation), so there is no "this line is a heading because it
was bold in the source" signal available - only textual patterns already
present in the extracted characters themselves (markdown `#` headings,
blank-line paragraph breaks, `-`/`*`/numbered list markers, ` ``` ` code
fences, `|...|` table rows, and a conservative heuristic for a short,
isolated, capitalised standalone line).

`source_type` changes how a single newline is interpreted, because
`text_extraction.py` encodes paragraph boundaries differently per format:

- `docx`: `_extract_docx` joins each python-docx paragraph with a single
  "\\n" - every line break IS a real paragraph boundary.
- `pdf`/others: `_extract_pdf` (via pypdf) inserts a "\\n" at each *visual*
  line within a page, which is frequently a soft line-wrap in the middle of
  one logical paragraph, not a paragraph boundary - only a *blank* line
  reliably separates paragraphs for these source types, so soft-wrapped
  lines are rejoined with a space.

Getting this wrong in either direction would either shred prose (docx) into
one-line paragraphs into meaningless fragments (pdf/txt), so this
distinction is load-bearing, not cosmetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_BLOCK = "list_block"
    CODE_BLOCK = "code_block"
    TABLE_BLOCK = "table_block"


@dataclass(frozen=True)
class StructuralBlock:
    block_type: BlockType
    text: str
    # Only set for BlockType.HEADING. Markdown headings (`#`..`######`) get
    # their real level (1-6); the heuristic (non-markdown) standalone-line
    # heading always gets level 1, since there is no reliable way to infer
    # sub-levels without an explicit marker - see module docstring.
    heading_level: int | None = None


# Source types for which text_extraction.py's line breaks are real paragraph
# boundaries rather than soft visual wraps - see module docstring.
_LINE_IS_PARAGRAPH_BOUNDARY_SOURCE_TYPES = {"docx"}

_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(\S.*)$")
_LIST_ITEM = re.compile(r"^\s{0,3}(?:[-*•]|\d{1,3}[.)])\s+\S")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_CODE_FENCE = re.compile(r"^\s*```")
_MAX_HEURISTIC_HEADING_CHARS = 90
_HEURISTIC_HEADING_TERMINATORS = (".", ",", ";")


def _looks_like_heuristic_heading(line: str) -> bool:
    """A short, standalone line with no sentence-ending punctuation, that is
    either ALL-CAPS or Title-Cased-ish - the same conservative pattern a
    human skimming plain text would themselves use to spot a heading.
    Deliberately conservative (false negatives are safe - the line just
    becomes a normal paragraph instead; false positives are not, since they
    would incorrectly restart the heading_path)."""
    if not line or len(line) > _MAX_HEURISTIC_HEADING_CHARS:
        return False
    if line.endswith(_HEURISTIC_HEADING_TERMINATORS):
        return False
    words = line.split()
    if not words:
        return False
    if line.isupper() and any(char.isalpha() for char in line):
        return True
    # Title Case: every word starting with a letter is capitalised (allows
    # short lowercase connector words like "of"/"and"/"the"/"for"/"to").
    _CONNECTORS = {"of", "and", "the", "for", "to", "a", "an", "in", "on", "vs", "at", "or"}
    letter_words = [word for word in words if word[0].isalpha()]
    if len(letter_words) < 1:
        return False
    capitalised = sum(1 for word in letter_words if word[0].isupper() or word.lower() in _CONNECTORS)
    return capitalised == len(letter_words) and len(letter_words) <= 12


def parse_structural_blocks(text: str, *, source_type: str = "generic") -> list[StructuralBlock]:
    if not text or not text.strip():
        return []

    lines = text.split("\n")
    total = len(lines)
    line_is_paragraph_boundary = source_type in _LINE_IS_PARAGRAPH_BOUNDARY_SOURCE_TYPES

    blocks: list[StructuralBlock] = []
    index = 0
    while index < total:
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if _CODE_FENCE.match(line):
            start = index
            index += 1
            while index < total and not _CODE_FENCE.match(lines[index]):
                index += 1
            end = min(index + 1, total)
            block_text = "\n".join(lines[start:end])
            blocks.append(StructuralBlock(block_type=BlockType.CODE_BLOCK, text=block_text))
            index = end
            continue

        heading_match = _MARKDOWN_HEADING.match(stripped)
        if heading_match:
            blocks.append(
                StructuralBlock(block_type=BlockType.HEADING, text=heading_match.group(2).strip(), heading_level=len(heading_match.group(1)))
            )
            index += 1
            continue

        if _TABLE_ROW.match(line):
            start = index
            while index < total and _TABLE_ROW.match(lines[index]):
                index += 1
            block_text = "\n".join(candidate.strip() for candidate in lines[start:index])
            blocks.append(StructuralBlock(block_type=BlockType.TABLE_BLOCK, text=block_text))
            continue

        if _LIST_ITEM.match(line):
            start = index
            while index < total and lines[index].strip() and (_LIST_ITEM.match(lines[index]) or lines[index].startswith((" ", "\t"))):
                index += 1
            block_text = "\n".join(candidate.strip() for candidate in lines[start:index])
            blocks.append(StructuralBlock(block_type=BlockType.LIST_BLOCK, text=block_text))
            continue

        # "Isolated" means "surrounded by blank lines" for source types where
        # a blank line is the real paragraph separator (pdf/txt/csv/generic).
        # For docx, every line is already its own paragraph (see module
        # docstring) - blank lines essentially never appear, so requiring
        # blank-line isolation would mean this heuristic never fires at all;
        # being its own line already satisfies the same "standalone" intent.
        if line_is_paragraph_boundary:
            isolated = True
        else:
            next_stripped = lines[index + 1].strip() if index + 1 < total else ""
            prev_stripped = lines[index - 1].strip() if index > 0 else ""
            isolated = not prev_stripped and not next_stripped
        if isolated and _looks_like_heuristic_heading(stripped):
            blocks.append(StructuralBlock(block_type=BlockType.HEADING, text=stripped, heading_level=1))
            index += 1
            continue

        # Paragraph: either exactly one line (docx - every line break is a
        # real boundary) or a run of non-blank lines up to the next blank
        # line / structural marker, soft-wrapped lines rejoined with a space
        # (pdf/txt/csv/generic - see module docstring).
        start = index
        para_lines = [stripped]
        index += 1
        if not line_is_paragraph_boundary:
            while index < total:
                candidate = lines[index]
                candidate_stripped = candidate.strip()
                if not candidate_stripped:
                    break
                if _CODE_FENCE.match(candidate) or _MARKDOWN_HEADING.match(candidate_stripped) or _TABLE_ROW.match(candidate) or _LIST_ITEM.match(candidate):
                    break
                para_lines.append(candidate_stripped)
                index += 1
        blocks.append(StructuralBlock(block_type=BlockType.PARAGRAPH, text=" ".join(para_lines)))

    return blocks
