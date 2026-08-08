# Vector Storage Architecture

## Storage

- `Chunk.embedding_vector` uses a custom `PgVector` SQLAlchemy type (`app.db.types`): compiles to `vector(N)` on PostgreSQL (pgvector extension), and to plain `TEXT` on SQLite.
- **SQLite never actually stores a usable vector.** `embed_document_version_chunks()` only writes `embedding_vector` when `db.bind.dialect.name == "postgresql"`. On SQLite, cosine similarity is recomputed live in Python at query time by re-embedding each candidate chunk's content on the fly (`_cosine_similarity` in `app.services.vector_search`). This is a real functional difference between local dev/tests and production — don't assume SQLite-passing behavior proves the Postgres vector-search path is correct too; if the change touches search ranking specifically, verify against Postgres if possible.

## Search

`app.services.vector_search.search_embedded_chunks()` branches on `db.bind.dialect.name`:

- **Postgres** (`_search_postgresql`) — raw SQL using pgvector's `<=>` cosine-distance operator, `ORDER BY ... <=> ... LIMIT`.
- **SQLite** (`_search_sqlite`) — ORM fetch of candidate rows, Python-side cosine similarity, manual sort/truncate.

Both paths filter on `Chunk.organisation_id`, `Chunk.workspace_id`, `Chunk.status == "ready"`, and (critically) `document_ids` for knowledge scope — see `retrieval.md`'s "Knowledge scoping" for the `None` vs `[]` semantics.

## Multi-provider coexistence

`embedding_provider`, `embedding_model`, and `embedding_dimension` are all part of the search WHERE filter, on both dialects. A query only ever matches chunks embedded by the *exact same* provider/model/dimension triple. This means multiple embedding providers' vectors can coexist in the same `chunks` table without cross-contamination — switching a workspace's configured provider effectively partitions which chunks are retrievable until they're re-embedded with the new provider.

## Providers

`app.services.embeddings.EmbeddingProvider` (protocol) implementations:

- `LocalMockEmbeddingProvider` — SHA-256 hash-based, deterministic, **not semantically meaningful**. Its similarity scores should not be trusted for relevance reasoning — see the note in `RETRIEVAL_MIN_SIMILARITY_SCORE`'s own code comment (defaults to `0.0` specifically because of this).
- `FailingEmbeddingProvider` — always raises, for failure-mode tests.
- `OllamaEmbeddingProvider` — real local semantic embeddings via a running Ollama server's `/api/embed`. No live cloud embedding provider (OpenAI, etc.) exists yet.

## Rules

- Never assume SQLite test-passing means the Postgres vector path is correct for a search-ranking change — the two code paths are genuinely different implementations of the same contract.
- Never compare similarity scores across different embedding providers/models — they aren't on a comparable scale, and the mock provider's scores aren't meaningful at all.
- If adding a new embedding provider, implement the `EmbeddingProvider` protocol and register it in `build_embedding_provider()` — don't special-case it in `vector_search.py`.
