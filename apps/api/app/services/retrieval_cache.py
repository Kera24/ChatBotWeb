"""Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md,
Part 13) - a bounded, content-addressed retrieval/semantic-query cache.
Mirrors app.access.rate_limit.redis_store's exact
Protocol/InMemory/Redis-backed pattern (this project's existing precedent
for "start with an in-process or existing Redis-compatible abstraction",
`settings.REDIS_URL` is already part of this deployment's VPS architecture -
see docker-compose.yml's `redis` service).

Two of the three cache types Part 13 asks for are already covered elsewhere
and NOT reimplemented here:
- Embedding cache: app.evaluation.embedding_cache.CachingEmbeddingProvider
  already exists (memoises EmbeddingProvider.embed() by exact
  (provider, model, dimension, content-hash)) - generic, not evaluation-
  specific in its implementation even though only evaluation wires it in
  today.
- Final generated ANSWERS are deliberately never cached here (Part 13's
  explicit "do NOT cache final generated answers by default during this
  experiment").

This module is the other two: a retrieval-result cache (B) and, since a
normalized-query-text key is exactly what makes B double as a lightweight
semantic-query cache (C) without the correctness risk of a fuzzy/embedding-
similarity cache (which could return a WRONG cached answer for a
similar-but-different question - explicitly out of scope for a bounded,
first-pass cache), both are the same mechanism here.

Content-addressed invalidation ("a knowledge update must invalidate stale
retrieval/cache entries", Part 13): the cache key includes a
`knowledge_revision` component - the latest `Document.updated_at` among the
assistant's in-scope documents. A document update changes this automatically,
so a stale entry is never read again (it simply becomes an orphaned, TTL-
expired key) - no active invalidation/pub-sub required, matching "do not
build distributed caching infrastructure yet".

Never cross-tenant: organisation_id/workspace_id/assistant scope are baked
into the cache key itself, not just used as a lookup filter after the fact -
there is no code path that can read one tenant's cached retrieval result for
another tenant's request.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Protocol

_DEFAULT_TTL_SECONDS = 300


@dataclass(frozen=True)
class RetrievalCacheKeyParts:
    query: str
    organisation_id: str
    workspace_id: str
    assistant_id: str | None
    knowledge_revision: str
    embedding_provider: str
    embedding_model: str
    retrieval_strategy_version: str
    prompt_version: str | None = None

    def normalized_query(self) -> str:
        # Case/whitespace normalization only (Part 13's "normalized
        # query/hash") - NOT a semantic/embedding-similarity match. Two
        # genuinely different questions must never collide.
        return re.sub(r"\s+", " ", self.query.strip().lower())

    def cache_key(self) -> str:
        payload = "|".join([
            self.normalized_query(), self.organisation_id, self.workspace_id, self.assistant_id or "-",
            self.knowledge_revision, self.embedding_provider, self.embedding_model,
            self.retrieval_strategy_version, self.prompt_version or "-",
        ])
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        # Tenant id kept as a readable key PREFIX (not just inside the hash)
        # so an operator inspecting Redis keys can see which tenant a cache
        # entry belongs to without decoding the hash - a defence-in-depth
        # readability aid, not the isolation mechanism itself (the hash
        # already includes it).
        return f"retrieval_cache:{self.organisation_id}:{digest}"


@dataclass(frozen=True)
class CachedRetrievalEntry:
    """Lightweight, self-contained (no DB re-fetch needed) serialisable
    snapshot of a retrieval result - chunk-level provenance only, never raw
    prompt/generation content (this is a retrieval cache, not an answer
    cache)."""

    chunk_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    scores: tuple[float, ...]
    cached_at: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(raw: str) -> "CachedRetrievalEntry":
        data = json.loads(raw)
        return CachedRetrievalEntry(
            chunk_ids=tuple(data["chunk_ids"]), document_ids=tuple(data["document_ids"]),
            scores=tuple(data["scores"]), cached_at=data["cached_at"],
        )


class RetrievalCacheStore(Protocol):
    def get(self, key: str) -> CachedRetrievalEntry | None: ...
    def set(self, key: str, entry: CachedRetrievalEntry, *, ttl_seconds: int) -> None: ...
    def health_check(self) -> bool: ...


@dataclass
class InMemoryRetrievalCacheStore:
    """Per-process dict with TTL - the default when Redis is not configured/
    reachable, matching app.access.rate_limit.local_fallback's exact
    fail-open rationale (cache unavailability must never break retrieval,
    only forgo the speedup)."""

    _entries: dict[str, tuple[float, CachedRetrievalEntry]] | None = None
    hits: int = 0
    misses: int = 0

    def __post_init__(self) -> None:
        if self._entries is None:
            self._entries = {}

    def get(self, key: str) -> CachedRetrievalEntry | None:
        stored = self._entries.get(key)
        if stored is None:
            self.misses += 1
            return None
        expires_at, entry = stored
        if expires_at < time.monotonic():
            del self._entries[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry

    def set(self, key: str, entry: CachedRetrievalEntry, *, ttl_seconds: int) -> None:
        self._entries[key] = (time.monotonic() + ttl_seconds, entry)

    def health_check(self) -> bool:
        return True

    def stats(self) -> dict[str, int]:
        return {"cache_hit_count": self.hits, "cache_miss_count": self.misses, "cache_size": len(self._entries or {})}


@dataclass
class RedisRetrievalCacheStore:
    redis_client: object
    hits: int = 0
    misses: int = 0

    def get(self, key: str) -> CachedRetrievalEntry | None:
        try:
            raw = self.redis_client.get(key)
        except Exception:
            # Fail-safe, not fail-loud: a Redis outage degrades to "always
            # miss" (retrieval still runs normally), never an exception that
            # would take retrieval itself down - same guarantee
            # app.access.rate_limit.local_fallback documents for rate
            # limiting.
            self.misses += 1
            return None
        if raw is None:
            self.misses += 1
            return None
        self.hits += 1
        return CachedRetrievalEntry.from_json(raw.decode("utf-8") if isinstance(raw, bytes) else raw)

    def set(self, key: str, entry: CachedRetrievalEntry, *, ttl_seconds: int) -> None:
        try:
            self.redis_client.set(key, entry.to_json(), ex=ttl_seconds)
        except Exception:
            pass  # best-effort - a failed cache write must never fail the request it's attached to

    def health_check(self) -> bool:
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False

    def stats(self) -> dict[str, int]:
        return {"cache_hit_count": self.hits, "cache_miss_count": self.misses}


def knowledge_revision_for_scope(db, *, organisation_id: str, workspace_id: str, document_ids: list[str] | None) -> str:
    """The cache-invalidation signal (Part 13's "a knowledge update must
    invalidate stale retrieval/cache entries"): the latest `Document.updated_at`
    among the in-scope documents, as an ISO string (or "empty" for an
    explicitly-empty scope, "unscoped" for no restriction). A document
    update, publish, or archive bumps its own `updated_at`
    (TimestampMixin's `onupdate`), which changes this value and therefore
    the whole cache key - no separate cache-invalidation bookkeeping needed."""
    from sqlalchemy import func, select

    from app.db.models import Document

    if document_ids is not None and len(document_ids) == 0:
        return "empty"
    statement = select(func.max(Document.updated_at)).where(Document.organisation_id == organisation_id, Document.workspace_id == workspace_id)
    if document_ids:
        statement = statement.where(Document.id.in_(document_ids))
    latest = db.execute(statement).scalar()
    return latest.isoformat() if latest is not None else "unscoped"


def build_retrieval_cache_store(*, redis_url: str | None, timeout_seconds: float = 1.0) -> RetrievalCacheStore:
    """Fails open to InMemoryRetrievalCacheStore (never raises) - this cache
    is a pure optimisation, so a missing/unreachable Redis must degrade to
    "cache always misses, retrieval still works", never to a startup or
    request failure."""
    if not redis_url:
        return InMemoryRetrievalCacheStore()
    try:
        from app.access.rate_limit.redis_store import create_redis_client

        client = create_redis_client(redis_url=redis_url, timeout_seconds=timeout_seconds)
        client.ping()
        return RedisRetrievalCacheStore(client)
    except Exception:
        return InMemoryRetrievalCacheStore()
