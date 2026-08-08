# ADR-0019: PostgreSQL + pgvector Over a Dedicated Vector Database

Status: Accepted
Date: 2026-08-07

## Context

The RAG pipeline (`docs/architecture/retrieval.md`) needs a vector similarity search backend for chunk embeddings (`Chunk.embedding_vector`, `docs/architecture/vector-storage.md`). At the time this decision was made, the platform was pre-launch with a small number of pilot tenants, no measured retrieval-latency problem, and Postgres already the system of record for every other relational entity (organisations, workspaces, documents, conversations, evaluation data).

## Decision

Use PostgreSQL with the `pgvector` extension as the single vector store, for both relational and vector data, rather than introducing a dedicated vector database (e.g. Qdrant, Pinecone, Weaviate) at launch.

## Alternatives

- **Dedicated vector database (Qdrant)** — purpose-built ANN indexes, likely better recall/latency at large scale. Rejected for now: adds a second stateful service to operate, a second data-consistency boundary (documents live in Postgres, vectors would live elsewhere), and no evidence yet that pgvector is a bottleneck. See `docs/adr/0020-delay-qdrant-migration.md` and `docs/future/QdrantMigration.md` for the deferred path and its triggers.
- **Managed vector-search SaaS (Pinecone, etc.)** — removes operational burden but adds a third-party dependency with its own pricing/availability risk, and duplicates data that already lives in Postgres. Rejected for the same reasons as above, plus vendor lock-in concerns (see `docs/principles/engineering-principles.md`'s vendor independence principle).

## Tradeoffs

- Gains: one database to operate/back up/restore (`deployment/backup/backup.sh` already covers it), transactional consistency between a document row and its chunk vectors, no new infrastructure for the VPS pilot deployment (`docs/adr/0027-vps-first-controlled-pilot-hosting.md`).
- Costs: pgvector's ANN indexing (IVFFlat/HNSW) is generally slower and less tunable than a purpose-built vector engine at large corpus sizes; write path is dialect-conditional (SQLite dev/test has no real vector index) — see `docs/architecture/vector-storage.md`.

## Consequences

- All retrieval code must go through `app.services.vector_search`, never a second vector client.
- Vector-store scaling and Postgres scaling are coupled — a future need to scale one may force scaling both.

## Future reconsideration triggers

- Measured retrieval latency or recall degradation attributable to pgvector at production data volumes (see `docs/engineering/scaling-strategy.md`'s customer-count tiers).
- Corpus size per tenant or in aggregate crossing the point where `docs/future/QdrantMigration.md`'s stated triggers are met.
