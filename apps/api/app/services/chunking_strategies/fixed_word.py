from __future__ import annotations

from dataclasses import dataclass

from app.services.chunking_strategies.base import ChunkingConfig, ChunkSpan


@dataclass(frozen=True)
class FixedWordChunkingStrategy:
    """The existing/current production strategy - kept available so a
    regression in a new strategy can always be rolled back by switching
    `CHUNKING_STRATEGY` back to `"fixed_word"` with no code change.

    Delegates to `app.services.chunking.split_text_into_chunks` (the exact
    function production has used since launch) rather than reimplementing
    fixed-size splitting here, so this strategy's output is byte-for-byte
    identical to today's behaviour - not just "similar"."""

    strategy_key: str = "fixed_word"
    # Matches app.services.chunking.CHUNKING_STRATEGY_VERSION exactly - both
    # names for the same one baseline algorithm.
    strategy_version: str = "mvp-word-v1"

    def chunk(self, text: str, *, config: ChunkingConfig) -> list[ChunkSpan]:
        # Local import: app.services.chunking imports this package to build
        # the strategy the caller asked for, so a module-level import here
        # would be circular. Deferring it to call time (long after both
        # modules have finished importing) breaks the cycle safely.
        from app.services.chunking import split_text_into_chunks

        pieces = split_text_into_chunks(text, chunk_size_words=config.chunk_size_words, chunk_overlap_words=config.chunk_overlap_words)
        return [ChunkSpan(content=piece) for piece in pieces]
