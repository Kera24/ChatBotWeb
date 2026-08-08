# Qdrant Migration

## Purpose

Migrate vector storage/search from PostgreSQL+pgvector to a dedicated vector database (Qdrant) if and when scale makes pgvector's ANN performance a measured bottleneck.

## Current limitation

pgvector's IVFFlat/HNSW indexing is less tunable and generally slower at large corpus sizes than purpose-built vector engines; no current tenant/corpus size has hit this limit.

## Why postponed

`docs/adr/0019-postgresql-pgvector-over-dedicated-vector-database.md` and `docs/adr/0020-delay-qdrant-migration.md` — no measured evidence of a pgvector bottleneck exists yet, and running a second stateful service adds real operational cost that isn't justified without that evidence.

## Dependencies

- `app.services.vector_search` must stay a clean abstraction boundary (no pgvector-specific SQL leaking into orchestrator/business logic) — this is what makes the migration a swap rather than a rewrite.
- Observability cost/latency trace data (`docs/architecture/observability.md`) to establish the trigger has actually been hit.
- `docs/engineering/scaling-strategy.md`'s customer-count tiers, to know which tier this becomes relevant at.

## Implementation phases

1. Stand up Qdrant in a non-production environment; dual-write embeddings (Postgres remains source of truth for chunk metadata, Qdrant holds vectors) behind a flag.
2. Implement `app.services.vector_search`'s interface against Qdrant; run retrieval evaluation side-by-side against the pgvector path.
3. Shadow-read comparison in production (compute both, serve pgvector, log divergence) before cutting over.
4. Cutover per-workspace or globally once shadow comparison shows parity or improvement.
5. Decommission pgvector vector columns after a safe retention window (keep the migration reversible until then).

## Technical design

Qdrant deployed as an additional VPS service (or managed Qdrant Cloud, cost-dependent); `Chunk` rows keep a `qdrant_point_id` reference; embedding writes become dual-target during migration, single-target (Qdrant) after cutover.

## Evaluation plan

Retrieval precision/recall parity or improvement vs. the existing pgvector baseline on the standard evaluation case set, plus p95 retrieval latency comparison under realistic query volume.

## Rollback strategy

Dual-write phase makes rollback trivial (flip the read flag back to pgvector). After decommissioning pgvector vectors, rollback requires re-embedding from `DocumentVersion` source text — acceptable since documents remain the source of truth throughout.

## Success metrics

Measured retrieval latency/recall improvement at the trigger scale, with no regression in evaluation gate pass rate during and after migration.
