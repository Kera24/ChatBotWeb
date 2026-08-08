# Skill: Retrieval / Vector Search

## Purpose

Work on embedding generation, vector storage, or the vector-search query path specifically (narrower than the `rag` skill, which covers the whole orchestrator).

## When to use

Any task touching `apps/api/app/services/{vector_search,embeddings,retrieval_context}.py`, `apps/api/app/db/models/chunk.py`, or `apps/api/app/db/types.py`'s `PgVector` type. Full reference: `docs/architecture/vector-storage.md`.

## Architecture assumptions

- pgvector on Postgres (real vector column + `<=>` cosine-distance operator); SQLite has no real vector column — cosine similarity is recomputed in Python at query time.
- `embedding_provider`/`embedding_model`/`embedding_dimension` are part of every search's WHERE filter — multiple providers coexist in one table by exact-triple partitioning, never cross-matched.
- The mock embedding provider's similarity scores are not semantically meaningful (SHA-256 hash-based) — don't reason about relevance from mock-provider scores.

## Files typically modified

- `apps/api/app/services/vector_search.py`
- `apps/api/app/services/embeddings.py`
- `apps/api/app/services/retrieval_context.py`
- `apps/api/app/db/models/chunk.py` / `apps/api/app/db/types.py` (only for genuine schema-level changes)

## Files never modified

- Knowledge-scope resolution semantics (`document_ids=None` vs `[]`) in `rag_orchestrator.py` — that's the `rag` skill's territory, and this specific distinction is tenant-isolation-adjacent.
- The provider/model/dimension triple-matching filter — removing it would let embeddings from different providers cross-match incorrectly.

## Validation commands

```
npm run api:test
```
Specifically re-run `apps/api/tests/test_vector_search_similarity_threshold.py` and `test_ollama_embedding_provider.py` if touching search ranking or a real provider.

## Expected report format

Full Report if the Postgres and SQLite paths could now behave differently, or if a new provider was added; Short Report for a narrow bugfix confirmed identical on both dialects.

## Common pitfalls

- Changing `_search_sqlite`/`_search_postgresql` without updating both — they must remain functionally equivalent even though they're implemented differently.
- Assuming SQLite test-passing proves Postgres correctness for a ranking change.
- Adding a new embedding provider without implementing the full `EmbeddingProvider` protocol, causing a silent type mismatch at call time instead of a clear error.

## Best practices

- When adding a new embedding provider, implement `EmbeddingProvider` and register it in `build_embedding_provider()` — don't special-case it in `vector_search.py`.
- Test similarity-threshold changes against `Ollama` (real semantic embeddings) if available, not just the mock provider, since mock scores aren't meaningful for relevance judgments.
