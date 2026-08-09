"""Phase 3: structure-aware chunking.

Groups the document into logical sections by walking its heading hierarchy
(`app.services.chunking_strategies.structure_parser`), then packs each
section's blocks into size-bounded chunks - preferring to keep a whole
subsection together, only splitting on a raw word boundary when a section
(or a single oversized block within it - a huge paragraph, list, or table)
exceeds `max_chunk_size_words`. Falls back to the exact same word-splitting
`chunk_document_version` has always used
(`app.services.chunking.split_text_into_chunks`) for that oversized case, so
"structure-aware" never means "loses the safety net the current strategy
already has for pathological input."
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.chunking_strategies.base import ChunkingConfig, ChunkSpan
from app.services.chunking_strategies.structure_parser import BlockType, StructuralBlock, parse_structural_blocks


@dataclass
class _Section:
    heading_path: str | None
    section_title: str | None
    section_ordinal: int
    blocks: list[StructuralBlock]


def _build_sections(blocks: list[StructuralBlock]) -> list[_Section]:
    """Walks blocks in document order, maintaining a heading-level stack, and
    groups every non-heading block under the section whose heading most
    recently preceded it. Content before the first heading becomes its own
    "preamble" section with heading_path/section_title left None - honest
    about there being no heading, rather than fabricating one."""
    sections: list[_Section] = []
    stack: list[tuple[int, str]] = []  # (level, text)
    current = _Section(heading_path=None, section_title=None, section_ordinal=0, blocks=[])
    ordinal = 0

    def start_new_section() -> None:
        nonlocal current, ordinal
        if current.blocks:
            sections.append(current)
        ordinal += 1
        heading_path = " > ".join(text for _level, text in stack) or None
        section_title = stack[-1][1] if stack else None
        current = _Section(heading_path=heading_path, section_title=section_title, section_ordinal=ordinal, blocks=[])

    for block in blocks:
        if block.block_type == BlockType.HEADING:
            level = block.heading_level or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, block.text))
            start_new_section()
            # The heading text itself becomes the section's first block, so
            # each chunk's content is self-contained/readable on its own,
            # not just tagged via heading_path/section_title metadata.
            current.blocks.append(block)
            continue
        current.blocks.append(block)

    if current.blocks:
        sections.append(current)
    return sections


def _block_text_for_content(block: StructuralBlock) -> str:
    if block.block_type == BlockType.HEADING:
        return block.text
    if block.block_type == BlockType.LIST_BLOCK:
        return block.text
    return block.text


def _pack_section_into_chunks(section: _Section, *, config: ChunkingConfig) -> list[ChunkSpan]:
    from app.services.chunking import split_text_into_chunks

    chunks: list[ChunkSpan] = []
    current_parts: list[str] = []
    current_block_types: list[str] = []
    current_words = 0

    def flush(*, split_reason: str) -> None:
        nonlocal current_parts, current_block_types, current_words
        if not current_parts:
            return
        content = "\n\n".join(current_parts)
        chunks.append(
            ChunkSpan(
                content=content,
                heading_path=section.heading_path,
                section_title=section.section_title,
                metadata={
                    "section_key": f"{section.section_ordinal}:{section.heading_path or 'preamble'}",
                    "split_reason": split_reason,
                    "block_types": current_block_types,
                },
            )
        )
        current_parts = []
        current_block_types = []
        current_words = 0

    for block in section.blocks:
        block_text = _block_text_for_content(block)
        block_words = len(block_text.split())
        if block_words == 0:
            continue

        if block_words > config.max_chunk_size_words:
            # A single block (huge paragraph/list/table) too big to ever fit
            # in one chunk on its own - flush whatever preceded it, then
            # fall back to plain word-splitting for just this block, still
            # carrying the section's heading context on every piece.
            flush(split_reason="size_limit")
            for piece in split_text_into_chunks(block_text, chunk_size_words=config.chunk_size_words, chunk_overlap_words=config.chunk_overlap_words):
                chunks.append(
                    ChunkSpan(
                        content=piece,
                        heading_path=section.heading_path,
                        section_title=section.section_title,
                        metadata={
                            "section_key": f"{section.section_ordinal}:{section.heading_path or 'preamble'}",
                            "split_reason": "oversized_block",
                            "block_types": [block.block_type.value],
                        },
                    )
                )
            continue

        if current_words + block_words > config.max_chunk_size_words and current_words >= config.min_chunk_size_words:
            flush(split_reason="size_limit")

        current_parts.append(block_text)
        current_block_types.append(block.block_type.value)
        current_words += block_words

        if current_words >= config.chunk_size_words:
            flush(split_reason="size_limit")

    flush(split_reason="section_boundary")

    # Avoid a tiny trailing fragment: if the last chunk in this section is
    # under min_chunk_size_words and there is a predecessor in the same
    # section, merge them rather than emitting a pathologically small chunk.
    if len(chunks) >= 2:
        last = chunks[-1]
        if len(last.content.split()) < config.min_chunk_size_words:
            previous = chunks[-2]
            merged = ChunkSpan(
                content=f"{previous.content}\n\n{last.content}",
                heading_path=previous.heading_path,
                section_title=previous.section_title,
                metadata={**previous.metadata, "merged_trailing_fragment": True},
            )
            chunks[-2:] = [merged]

    return chunks


@dataclass(frozen=True)
class StructureAwareChunkingStrategy:
    strategy_key: str = "structure_aware"
    strategy_version: str = "structure-aware-v1"

    def chunk(self, text: str, *, config: ChunkingConfig) -> list[ChunkSpan]:
        blocks = parse_structural_blocks(text, source_type=config.source_type)
        if not blocks:
            return []
        sections = _build_sections(blocks)
        chunks: list[ChunkSpan] = []
        for section in sections:
            chunks.extend(_pack_section_into_chunks(section, config=config))
        return merge_undersized_chunks(chunks, config=config)


def merge_undersized_chunks(chunks: list[ChunkSpan], *, config: ChunkingConfig) -> list[ChunkSpan]:
    """Document-level pass merging any still-undersized chunk into a
    neighbour, across section boundaries. `_pack_section_into_chunks` only
    merges a small *trailing* chunk into its predecessor *within the same
    section* - it can't fix a whole section that produced exactly one tiny
    chunk (the common real case: a heading immediately followed by another,
    deeper heading, with no body content of its own - e.g. "# Company
    Handbook" directly followed by "## Vacation Policy"). Prefers merging
    forward into the next chunk (keeping the next chunk's more specific
    heading_path/section_title, since the tiny chunk was usually a broader
    parent heading with nothing substantive under it); falls back to
    merging backward for a trailing tiny chunk with no successor. Shared by
    both `StructureAwareChunkingStrategy` and `SemanticChunkingStrategy`."""
    if len(chunks) <= 1:
        return chunks
    result = list(chunks)
    index = 0
    while index < len(result):
        if len(result[index].content.split()) >= config.min_chunk_size_words:
            index += 1
            continue
        if index + 1 < len(result):
            following = result[index + 1]
            merged = ChunkSpan(
                content=f"{result[index].content}\n\n{following.content}",
                heading_path=following.heading_path,
                section_title=following.section_title,
                metadata={**following.metadata, "merged_undersized_chunk": True},
            )
            result[index : index + 2] = [merged]
            continue
        if index > 0:
            preceding = result[index - 1]
            merged = ChunkSpan(
                content=f"{preceding.content}\n\n{result[index].content}",
                heading_path=preceding.heading_path,
                section_title=preceding.section_title,
                metadata={**preceding.metadata, "merged_undersized_chunk": True},
            )
            result[index - 1 : index + 1] = [merged]
            index -= 1
            continue
        # Exactly one chunk total and it's under the minimum - a genuinely
        # tiny whole document; nothing left to merge into, keep it as-is.
        index += 1
    return result
