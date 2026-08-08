# ADR-0020: Delay Qdrant Migration

Status: Accepted
Date: 2026-08-07

## Context

`docs/adr/0019-postgresql-pgvector-over-dedicated-vector-database.md` chose pgvector for launch. Qdrant (or an equivalent dedicated vector database) is the most likely eventual upgrade path if retrieval scale outgrows pgvector, but building and operating a second stateful service before there is evidence it's needed would be premature.

## Decision

Do not begin a Qdrant migration now. Keep the vector-storage access path abstracted behind `app.services.vector_search` so a future migration is a swap behind that boundary, not a RAG-pipeline rewrite. Track the migration as a fully specified but explicitly postponed future feature: `docs/future/QdrantMigration.md`.

## Alternatives

- **Migrate now, ahead of need** — rejected: no current tenant or corpus size makes pgvector a measured bottleneck; would add operational surface area (a second stateful service, dual-write/consistency handling) with no corresponding evaluation-backed benefit (violates `docs/principles/engineering-principles.md`'s evidence-based decisions principle).
- **Never migrate, commit to pgvector permanently** — rejected: closes off a real scaling path without evidence it won't be needed; `docs/engineering/scaling-strategy.md`'s higher customer tiers explicitly may require it.

## Tradeoffs

- Gains: no premature operational complexity; migration effort is deferred until it's justified by evidence, and speccing it now (`docs/future/QdrantMigration.md`) means the team isn't starting from zero when the trigger fires.
- Costs: if scale arrives faster than expected, the migration becomes urgent rather than planned; the vector-search abstraction boundary must be kept honest (no pgvector-specific query leaking into orchestrator/business logic) or the eventual migration gets harder, not easier.

## Consequences

- Any code that queries vectors must go through `app.services.vector_search`'s interface, not raw pgvector SQL scattered across call sites — this is what keeps the migration option open.
- `docs/future/QdrantMigration.md` must be kept current as a real, actionable spec, not a placeholder, since it's the plan that gets executed when the trigger fires.

## Future reconsideration triggers

Same as `docs/adr/0019`'s triggers: measured pgvector latency/recall degradation, or corpus/tenant scale crossing the thresholds defined in `docs/future/QdrantMigration.md` and `docs/engineering/scaling-strategy.md`.
