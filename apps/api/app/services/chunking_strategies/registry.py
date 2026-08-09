from __future__ import annotations

from app.services.chunking_strategies.base import ChunkingStrategy
from app.services.chunking_strategies.fixed_word import FixedWordChunkingStrategy
from app.services.chunking_strategies.semantic import SemanticChunkingStrategy
from app.services.chunking_strategies.structure_aware import StructureAwareChunkingStrategy
from app.services.embeddings import EmbeddingProvider

# "fixed_word" is deliberately the default - the current production
# baseline. Phase 8 of the Knowledge Pipeline V2 spec: a new strategy only
# ever becomes the default after a bake-off shows it's non-regressive, never
# by default just because it exists. Rolling back after promotion is exactly
# "set CHUNKING_STRATEGY back to fixed_word" - no code change.
DEFAULT_STRATEGY_KEY = "fixed_word"

_NON_SEMANTIC_STRATEGY_BUILDERS = {
    "fixed_word": FixedWordChunkingStrategy,
    "structure_aware": StructureAwareChunkingStrategy,
}


class UnknownChunkingStrategy(ValueError):
    pass


def build_chunking_strategy(strategy_key: str, *, embedding_provider: EmbeddingProvider | None = None) -> ChunkingStrategy:
    """The single place a strategy key (as persisted in
    `Chunk.chunking_strategy_version`'s key half, or read from
    `settings.CHUNKING_STRATEGY`) resolves to a concrete implementation.

    `embedding_provider` is only required for `"structure_semantic"` - the
    other strategies never call an embedding provider during chunking
    (embedding happens later, per-chunk, in
    `app.services.embeddings.embed_document_version_chunks`, unchanged)."""
    if strategy_key in _NON_SEMANTIC_STRATEGY_BUILDERS:
        return _NON_SEMANTIC_STRATEGY_BUILDERS[strategy_key]()
    if strategy_key == "structure_semantic":
        if embedding_provider is None:
            raise UnknownChunkingStrategy(
                "The 'structure_semantic' chunking strategy requires an embedding_provider "
                "(it compares adjacent-unit similarity using the same EmbeddingProvider abstraction "
                "app.services.embeddings uses for real chunk embedding)."
            )
        return SemanticChunkingStrategy(embedding_provider=embedding_provider)
    raise UnknownChunkingStrategy(
        f"Unknown chunking strategy {strategy_key!r}. Supported: {sorted({*_NON_SEMANTIC_STRATEGY_BUILDERS, 'structure_semantic'})}."
    )
