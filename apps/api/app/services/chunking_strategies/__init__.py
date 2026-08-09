"""Knowledge Pipeline V2 - pluggable ChunkingStrategy abstraction.

Introduced so structure-aware and semantic chunking can be developed and
evaluated *alongside* the existing production chunker
(`app.services.chunking.split_text_into_chunks`/`chunk_document_version`),
never replacing it outright - see docs/engineering/chunking.md and
docs/architecture/knowledge-ingestion.md for the full picture.

    FixedWordChunkingStrategy    - the current production baseline, byte-
                                    for-byte identical to today's behaviour.
    StructureAwareChunkingStrategy - Phase 3: preserves heading/paragraph/
                                    list/table/code-block boundaries.
    SemanticChunkingStrategy     - Phase 4: structure-aware, plus embedding-
                                    similarity-based splitting for oversized
                                    sections.

`build_chunking_strategy(key)` is the single place a strategy key string
(persisted as `Chunk.chunking_strategy_version`, e.g. from
`settings.CHUNKING_STRATEGY`) resolves to an implementation.
"""

from app.services.chunking_strategies.base import ChunkingConfig, ChunkingStrategy, ChunkSpan
from app.services.chunking_strategies.fixed_word import FixedWordChunkingStrategy
from app.services.chunking_strategies.registry import (
    DEFAULT_STRATEGY_KEY,
    UnknownChunkingStrategy,
    build_chunking_strategy,
)
from app.services.chunking_strategies.semantic import SemanticChunkingStrategy
from app.services.chunking_strategies.structure_aware import StructureAwareChunkingStrategy

__all__ = [
    "ChunkingConfig",
    "ChunkingStrategy",
    "ChunkSpan",
    "FixedWordChunkingStrategy",
    "StructureAwareChunkingStrategy",
    "SemanticChunkingStrategy",
    "DEFAULT_STRATEGY_KEY",
    "UnknownChunkingStrategy",
    "build_chunking_strategy",
]
