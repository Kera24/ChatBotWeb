"""Unit tests for app.services.retrieval_cache (Retrieval & Answer Pipeline
V3 experiment, docs/future/RetrievalOptimisation.md Part 13) - the bounded
retrieval/semantic-query cache."""

import time

from app.services.retrieval_cache import (
    CachedRetrievalEntry,
    InMemoryRetrievalCacheStore,
    RetrievalCacheKeyParts,
    build_retrieval_cache_store,
)


def _key(**overrides) -> RetrievalCacheKeyParts:
    defaults = dict(
        query="How long is the free trial?", organisation_id="org1", workspace_id="ws1", assistant_id="asst1",
        knowledge_revision="rev1", embedding_provider="ollama", embedding_model="nomic-embed-text-v2-moe",
        retrieval_strategy_version="v3",
    )
    defaults.update(overrides)
    return RetrievalCacheKeyParts(**defaults)


def test_normalized_query_ignores_case_and_whitespace() -> None:
    a = _key(query="  How Long  is the free trial?  ")
    b = _key(query="how long is the free trial?")
    assert a.cache_key() == b.cache_key()


def test_different_question_produces_different_key() -> None:
    a = _key(query="How long is the free trial?")
    b = _key(query="How much does the Team plan cost?")
    assert a.cache_key() != b.cache_key()


def test_cross_tenant_keys_never_collide() -> None:
    a = _key(organisation_id="org1")
    b = _key(organisation_id="org2")
    assert a.cache_key() != b.cache_key()

    c = _key(workspace_id="ws1")
    d = _key(workspace_id="ws2")
    assert c.cache_key() != d.cache_key()

    e = _key(assistant_id="asst1")
    f = _key(assistant_id="asst2")
    assert e.cache_key() != f.cache_key()


def test_knowledge_revision_change_invalidates_the_key() -> None:
    a = _key(knowledge_revision="rev1")
    b = _key(knowledge_revision="rev2")
    assert a.cache_key() != b.cache_key()


def test_embedding_model_change_invalidates_the_key() -> None:
    a = _key(embedding_model="nomic-embed-text-v2-moe")
    b = _key(embedding_model="a-different-model")
    assert a.cache_key() != b.cache_key()


def test_retrieval_strategy_version_change_invalidates_the_key() -> None:
    a = _key(retrieval_strategy_version="v3")
    b = _key(retrieval_strategy_version="dense_only")
    assert a.cache_key() != b.cache_key()


def test_in_memory_store_hit_and_miss() -> None:
    store = InMemoryRetrievalCacheStore()
    key = _key().cache_key()
    assert store.get(key) is None  # miss before any write

    entry = CachedRetrievalEntry(chunk_ids=("c1", "c2"), document_ids=("d1", "d1"), scores=(0.9, 0.7), cached_at=time.time())
    store.set(key, entry, ttl_seconds=60)
    assert store.get(key) == entry
    assert store.stats()["cache_hit_count"] == 1
    assert store.stats()["cache_miss_count"] == 1


def test_in_memory_store_respects_ttl_expiry() -> None:
    store = InMemoryRetrievalCacheStore()
    key = _key().cache_key()
    entry = CachedRetrievalEntry(chunk_ids=("c1",), document_ids=("d1",), scores=(0.9,), cached_at=time.time())
    store.set(key, entry, ttl_seconds=-1)  # already expired
    assert store.get(key) is None


def test_cached_entry_json_roundtrip() -> None:
    entry = CachedRetrievalEntry(chunk_ids=("c1", "c2"), document_ids=("d1", "d2"), scores=(0.9, 0.5), cached_at=1234.5)
    restored = CachedRetrievalEntry.from_json(entry.to_json())
    assert restored == entry


def test_build_retrieval_cache_store_falls_back_to_in_memory_without_redis_url() -> None:
    store = build_retrieval_cache_store(redis_url=None)
    assert isinstance(store, InMemoryRetrievalCacheStore)


def test_build_retrieval_cache_store_fails_open_on_unreachable_redis() -> None:
    # An unreachable Redis must never raise or block startup - fails open to
    # the in-process store, same guarantee app.access.rate_limit.local_fallback
    # documents for rate limiting.
    store = build_retrieval_cache_store(redis_url="redis://127.0.0.1:1/0", timeout_seconds=0.2)
    assert isinstance(store, InMemoryRetrievalCacheStore)
