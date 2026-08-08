# SOP: Changing Vector Databases

## Purpose

Migrate vector storage (e.g. pgvector → Qdrant) without breaking retrieval or losing data, per `docs/future/QdrantMigration.md`.

## When to use

Only once `docs/adr/0020-delay-qdrant-migration.md`'s reconsideration triggers are actually met (measured pgvector latency/recall degradation) — not speculatively.

## Step-by-step process

1. Confirm `app.services.vector_search`'s abstraction boundary is still clean (no vector-store-specific SQL leaked into orchestrator/business logic) before starting.
2. Stand up the new vector store in a non-production environment.
3. Dual-write: new embeddings go to both stores; `Chunk` keeps a reference to the new store's identifier.
4. Implement `vector_search`'s interface against the new store.
5. Shadow-read comparison in production (compute both, serve the old store, log divergence).
6. Cut over per-workspace or globally once shadow comparison shows parity or improvement.
7. Decommission the old store's vector data after a safe retention window.

## Validation

`docs/checklists/retrieval-checklist.md`; retrieval latency/recall parity or improvement on the evaluation case set.

## Rollback

Dual-write phase makes rollback trivial (flip the read flag back). After old-store decommission, rollback requires re-embedding from `DocumentVersion` source text.

## Success criteria

Measured latency/recall improvement at the migration's trigger scale; zero data loss; no evaluation-gate regression during or after migration.
