from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ChunkingConfig:
    """Shared parameter surface every strategy receives. A strategy that
    doesn't use a given field (e.g. `FixedWordChunkingStrategy` ignores
    `min_chunk_size_words`/`semantic_similarity_threshold`) simply leaves it
    unused, rather than each strategy inventing its own config shape - this
    keeps `build_chunking_strategy()`'s call sites uniform regardless of
    which strategy is selected.

    `chunk_size_words`/`chunk_overlap_words` mirror the existing
    `CHUNK_SIZE_WORDS`/`CHUNK_OVERLAP_WORDS` settings (see
    app.services.chunking.split_text_into_chunks) - the structure-aware and
    semantic strategies still bound chunks to roughly this size, they just
    prefer a structural/semantic boundary over a raw word cut when one is
    available within range.
    """

    chunk_size_words: int
    chunk_overlap_words: int
    min_chunk_size_words: int = 40
    max_chunk_size_words: int = 500
    # Passed straight through to
    # app.services.chunking_strategies.structure_parser.parse_structural_blocks -
    # see that module's docstring for why a plain-text line break means
    # something different per source format (docx vs pdf/txt/csv). Strategies
    # that don't parse structure (FixedWordChunkingStrategy) ignore it.
    source_type: str = "generic"
    # None = "no similarity-based splitting" (structure-aware strategy
    # ignores this entirely). SemanticChunkingStrategy requires a real value;
    # see app.services.chunking_strategies.semantic's module docstring for
    # how the default was measured rather than guessed.
    semantic_similarity_threshold: float | None = None
    # A sentence/paragraph unit shorter than this is merged into its
    # neighbour before similarity comparison, so a single short sentence
    # can't become its own topic-shift boundary and produce a tiny fragment.
    semantic_min_unit_words: int = 12


@dataclass(frozen=True)
class ChunkSpan:
    """One candidate chunk produced by a ChunkingStrategy, before it becomes
    a `Chunk` ORM row. Maps onto `Chunk`'s existing columns 1:1 (see
    app.services.chunking.chunk_document_version) - no schema change was
    needed for any field here; every column already existed
    (`heading_path`/`section_title`/`page_number`/`chunking_strategy_version`
    on `Chunk`, JSON `metadata_json` for anything strategy-specific)."""

    content: str
    heading_path: str | None = None
    section_title: str | None = None
    page_number: int | None = None
    # Strategy-specific extras merged into Chunk.metadata_json - e.g.
    # {"section_key": ..., "split_reason": "size_limit" | "semantic_boundary",
    # "similarity_to_next": 0.41}. Deliberately free-form (JSON column) so a
    # new strategy never needs a schema change to record something new -
    # see Phase 5's parent/child-readiness note in
    # docs/engineering/chunking.md: `section_key` is exactly the grouping
    # field a future parent/child retriever would join sibling chunks on.
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkingStrategy(Protocol):
    """`strategy_key` + `strategy_version` together form the string persisted
    to `Chunk.chunking_strategy_version` (e.g. "structure_aware:structure-aware-v1")
    so a future re-index can always tell which strategy produced a given
    chunk - see app.services.chunking_strategies.registry.build_chunking_strategy
    and Phase 6 of docs/engineering/chunking.md."""

    strategy_key: str
    strategy_version: str

    def chunk(self, text: str, *, config: ChunkingConfig) -> list[ChunkSpan]: ...
