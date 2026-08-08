# Vector Storage — Current / Future / Out of Scope

## Current

Postgres+pgvector in production, SQLite fallback for dev/test (vector write path is dialect-conditional). Full detail: `docs/architecture/vector-storage.md`. Decision record: ADR 0019 (Postgres+pgvector over a dedicated vector database at current scale) and ADR 0020 (Qdrant migration delayed).

## Future

- Migration to a dedicated vector database (Qdrant) once scale/latency evidence justifies it — see `docs/future/QdrantMigration.md` and ADR 0020's reconsideration triggers.
- Hybrid (vector + keyword/BM25) retrieval — see `docs/future/HybridRetrieval.md`.

## Out of scope (not planned)

- Running two vector stores simultaneously as a permanent architecture (only as a transitional migration state, if/when the Qdrant migration is actually executed).
