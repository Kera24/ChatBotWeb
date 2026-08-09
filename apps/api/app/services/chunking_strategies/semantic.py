"""Phase 4: semantic chunking.

Extends structure-aware chunking (`structure_aware.py`): sections small
enough to fit in one chunk are packed exactly as the structure-aware
strategy does. Only an *oversized* section - one that would otherwise be
split on a raw word boundary - gets divided into sentence/paragraph units,
embedded via the existing `EmbeddingProvider` abstraction
(`app.services.embeddings`), and re-grouped at points where adjacent-unit
cosine similarity drops below a configured threshold (a likely topic
shift), instead of an arbitrary word-count cut.

Threshold, measured not guessed: `DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD`
(0.45) comes from comparing within-topic vs. cross-topic cosine similarity
using the real `nomic-embed-text-v2-moe` Ollama model against this
project's own golden evaluation corpus (`golden_dataset.json`, 14 real
product-documentation-style documents spanning 91 cross-document pairs):

    within-topic (same doc, two halves):  mean=0.571  p10=0.474  p90=0.649
    cross-topic  (different docs):        mean=0.299  p10=0.201  p90=0.436

0.45 sits between cross-topic's p90 (0.436, the upper edge of "different
topic" noise) and within-topic's p10 (0.474, the lower edge of "same topic"
signal) - the same midpoint methodology
`app.evaluation.embedding_config._VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL`
already uses for retrieval thresholds, kept in its own per-model map here
for the same reason: a similarity threshold is only meaningful relative to
one specific embedding model's score distribution, never a universal
constant. Re-measure before adding an entry for a new model.

This threshold is meaningless with `LocalMockEmbeddingProvider` (a SHA-256
hash with no semantic content - see that class's docstring and
tests/test_vector_search_similarity_threshold.py's same caveat elsewhere in
this codebase) - semantic chunking still runs mechanically against the mock
provider (useful for testing the *algorithm*), but topic-shift boundaries it
produces are not meaningful without a real embedding provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import sqrt

from app.services.chunking_strategies.base import ChunkingConfig, ChunkSpan
from app.services.chunking_strategies.structure_aware import (
    _Section,
    _block_text_for_content,
    _build_sections,
    _pack_section_into_chunks,
    merge_undersized_chunks,
)
from app.services.chunking_strategies.structure_parser import BlockType, parse_structural_blocks
from app.services.embeddings import EmbeddingProvider

DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD = 0.45

# Per-model calibrated thresholds - see module docstring for the
# measurement. Falls back to DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD for any
# unlisted model (including the mock provider) rather than refusing to run,
# since the algorithm is still exercised meaningfully in tests even when the
# specific numeric boundary isn't independently validated for that model.
_VALIDATED_SEMANTIC_SIMILARITY_THRESHOLD_BY_MODEL: dict[str, float] = {
    "nomic-embed-text-v2-moe": 0.45,
}


def recommended_semantic_similarity_threshold(model_name: str | None) -> float:
    if model_name is None:
        return DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD
    return _VALIDATED_SEMANTIC_SIMILARITY_THRESHOLD_BY_MODEL.get(model_name, DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD)


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def _split_into_sentences(text: str) -> list[str]:
    pieces = _SENTENCE_BOUNDARY.split(text.strip())
    return [piece.strip() for piece in pieces if piece.strip()]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    # Mirrors app.services.vector_search._cosine_similarity's formula
    # exactly - kept as a small local copy rather than importing that
    # module's private helper across a service boundary.
    if len(left) != len(right) or not left:
        return 0.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _section_word_count(section: _Section) -> int:
    return sum(len(_block_text_for_content(block).split()) for block in section.blocks)


def _section_to_units(section: _Section, *, config: ChunkingConfig) -> list[str]:
    """Breaks a section into sentence/paragraph comparison units. List/table/
    code blocks stay atomic (never split for semantic comparison - splitting
    mid-list or mid-table would produce a meaningless similarity signal and
    a confusing chunk boundary). A HEADING block is never its own unit
    either - comparing a heading's embedding against the body text's for a
    "topic shift" is a meaningless signal in the other direction (a heading
    is *introducing* the section, not competing with it for a boundary), so
    heading text is carried forward and prepended to the first real content
    unit that follows it instead. Only an oversized PARAGRAPH block is
    further divided into sentences, with tiny sentences merged forward up to
    `semantic_min_unit_words` so no unit is a one/two-word fragment on its
    own (Phase 4's "avoid tiny fragment chunks" applied at the unit level,
    before chunk boundaries are even decided)."""
    units: list[str] = []
    pending_heading_prefix: str | None = None

    def _append_unit(candidate: str) -> None:
        nonlocal pending_heading_prefix
        if pending_heading_prefix is not None:
            candidate = f"{pending_heading_prefix}\n\n{candidate}"
            pending_heading_prefix = None
        units.append(candidate)

    for block in section.blocks:
        text = _block_text_for_content(block)
        if block.block_type == BlockType.HEADING:
            pending_heading_prefix = f"{pending_heading_prefix}\n\n{text}" if pending_heading_prefix is not None else text
            continue

        words = len(text.split())
        if block.block_type != BlockType.PARAGRAPH or words <= config.max_chunk_size_words:
            _append_unit(text)
            continue

        sentences = _split_into_sentences(text)
        buffer: list[str] = []
        buffer_words = 0
        for sentence in sentences:
            buffer.append(sentence)
            buffer_words += len(sentence.split())
            if buffer_words >= config.semantic_min_unit_words:
                _append_unit(" ".join(buffer))
                buffer = []
                buffer_words = 0
        if buffer:
            if units and buffer_words < config.semantic_min_unit_words and pending_heading_prefix is None:
                units[-1] = f"{units[-1]} {' '.join(buffer)}"
            else:
                _append_unit(" ".join(buffer))

    # A section consisting of only heading(s) and nothing else - keep the
    # heading text as its own single unit rather than silently dropping it.
    if pending_heading_prefix is not None:
        units.append(pending_heading_prefix)
    return units


def _merge_undersized_groups(groups: list[list[int]], units: list[str], *, config: ChunkingConfig) -> list[list[int]]:
    if len(groups) <= 1:
        return groups
    merged: list[list[int]] = []
    for group in groups:
        group_words = sum(len(units[i].split()) for i in group)
        if merged and group_words < config.min_chunk_size_words:
            merged[-1].extend(group)
        else:
            merged.append(list(group))
    return merged


@dataclass(frozen=True)
class SemanticChunkingStrategy:
    embedding_provider: EmbeddingProvider
    strategy_key: str = "structure_semantic"
    strategy_version: str = "structure-semantic-v1"

    def chunk(self, text: str, *, config: ChunkingConfig) -> list[ChunkSpan]:
        threshold = (
            config.semantic_similarity_threshold
            if config.semantic_similarity_threshold is not None
            else recommended_semantic_similarity_threshold(self.embedding_provider.model_name)
        )
        blocks = parse_structural_blocks(text, source_type=config.source_type)
        if not blocks:
            return []
        sections = _build_sections(blocks)
        chunks: list[ChunkSpan] = []
        for section in sections:
            if _section_word_count(section) <= config.max_chunk_size_words:
                chunks.extend(_pack_section_into_chunks(section, config=config))
            else:
                chunks.extend(self._semantic_split_section(section, config=config, threshold=threshold))
        return merge_undersized_chunks(chunks, config=config)

    def _semantic_split_section(self, section: _Section, *, config: ChunkingConfig, threshold: float) -> list[ChunkSpan]:
        units = _section_to_units(section, config=config)
        if len(units) <= 1:
            # Nothing to compare (e.g. one giant list/table block) - the
            # structural packer already has a safe word-boundary fallback
            # for a single oversized block.
            return _pack_section_into_chunks(section, config=config)

        embeddings = [self.embedding_provider.embed(unit) for unit in units]
        similarities = [_cosine_similarity(embeddings[i], embeddings[i + 1]) for i in range(len(embeddings) - 1)]

        groups: list[list[int]] = [[0]]
        current_words = len(units[0].split())
        for i in range(1, len(units)):
            unit_words = len(units[i].split())
            topic_shift = similarities[i - 1] < threshold
            group_meets_min = current_words >= config.min_chunk_size_words
            would_exceed_max = current_words + unit_words > config.max_chunk_size_words
            if would_exceed_max or (topic_shift and group_meets_min):
                groups.append([i])
                current_words = unit_words
            else:
                groups[-1].append(i)
                current_words += unit_words

        groups = _merge_undersized_groups(groups, units, config=config)

        chunks: list[ChunkSpan] = []
        for group in groups:
            content = "\n\n".join(units[i] for i in group)
            boundary_similarity = similarities[group[-1]] if group[-1] < len(similarities) else None
            chunks.append(
                ChunkSpan(
                    content=content,
                    heading_path=section.heading_path,
                    section_title=section.section_title,
                    metadata={
                        "section_key": f"{section.section_ordinal}:{section.heading_path or 'preamble'}",
                        "split_reason": "semantic_boundary",
                        "semantic_similarity_threshold": threshold,
                        "similarity_to_next_unit": boundary_similarity,
                    },
                )
            )
        return chunks
