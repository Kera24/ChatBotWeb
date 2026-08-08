# Embeddings — Current / Future / Out of Scope

## Current

`app.services.embeddings.embed_document_version_chunks()`, provider built by `build_embedding_provider()` from `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION`. See `docs/architecture/knowledge-ingestion.md`'s "Processing pipeline" step 4 and `docs/architecture/vector-storage.md` for the write path.

## Future

- Multi-provider embedding bake-off (compare recall/precision across providers before committing to one at scale) — see `docs/future/EmbeddingBakeoff.md`.
- Query-side embedding cache to cut redundant embedding calls for repeated/near-duplicate questions — see `docs/future/CachingV2.md`.

## Out of scope (not planned)

- Re-embedding on every retrieval query against multiple providers simultaneously ("ensemble" embeddings) — one active provider per environment, not a runtime ensemble.
