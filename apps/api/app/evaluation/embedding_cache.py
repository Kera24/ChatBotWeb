"""Evaluation-only embedding memoisation (Retrieval V2 Phase 1 follow-up).

`app.services.vector_search._search_sqlite` has no vector index, so every
SQLite-backed retrieval call re-embeds every candidate chunk's content live
(see docs/architecture/vector-storage.md). Inside `app.evaluation.engine
.run_evaluation()` the SAME corpus is queried once per evaluation case, so a
104-case run against an N-chunk corpus makes ~N*104 redundant identical
embed() calls for chunk content alone - the dominant cost of a real-embedding
bake-off. `CachingEmbeddingProvider` memoises `embed()` by exact input text
scoped to one (provider, model, dimension) identity, so each unique chunk (or
query) is only ever embedded once per run, without touching
`app.services.vector_search`, `app.services.embeddings`, or any production
call path - this class is only ever constructed inside the evaluation engine.

Safety properties (see docs/architecture/evaluation.md and the retrieval
checklist):
- Purely additive memoisation of a pure function of (provider, model,
  dimension, text) - `embed()`'s return value is never altered, so retrieval
  ranking/scores are bit-for-bit identical whether or not caching is enabled.
- Cache key includes provider_name/model_name/dimension (the exact same
  triple `Chunk.embedding_provider/model/dimension` already partitions
  retrieval by - see vector-storage.md's "Multi-provider coexistence") plus a
  SHA-256 hash of the exact text, so a content change, a different model, or
  a different dimension can never collide with a cached entry.
- In-memory only, one dict per `CachingEmbeddingProvider` instance (one per
  `run_evaluation()` call) - never persisted, never shared across runs, and
  holds no customer-identifying data (SQLite evaluation fixtures only, per
  docs/architecture/evaluation.md - production document embedding never goes
  through this class).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

from app.services.embeddings import EmbeddingProvider


@dataclass
class CachingEmbeddingProvider:
    """Wraps any EmbeddingProvider with an exact-match memoisation cache.
    `hit_count`/`miss_count` are exposed for evaluation reporting (Retrieval
    V2 Phase 1 bake-off report's "embedding cache hit/miss counts")."""

    inner: EmbeddingProvider
    hit_count: int = field(default=0, init=False)
    miss_count: int = field(default=0, init=False)
    _cache: dict[tuple[str, str, int, str], list[float]] = field(default_factory=dict, init=False)

    @property
    def provider_name(self) -> str:
        return self.inner.provider_name

    @property
    def model_name(self) -> str:
        return self.inner.model_name

    @property
    def dimension(self) -> int:
        return self.inner.dimension

    def embed(self, text: str) -> list[float]:
        key = self._key(text)
        cached = self._cache.get(key)
        if cached is not None:
            self.hit_count += 1
            return cached
        self.miss_count += 1
        vector = self.inner.embed(text)
        self._cache[key] = vector
        return vector

    def _key(self, text: str) -> tuple[str, str, int, str]:
        content_hash = sha256(text.encode("utf-8")).hexdigest()
        return (self.inner.provider_name, self.inner.model_name, self.inner.dimension, content_hash)

    def stats(self) -> dict[str, int]:
        return {"embedding_cache_hit_count": self.hit_count, "embedding_cache_miss_count": self.miss_count}
