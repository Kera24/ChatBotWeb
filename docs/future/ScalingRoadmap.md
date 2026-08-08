# Scaling Roadmap

## Purpose

Define what changes and when as tenant/traffic scale grows, so scaling decisions are pre-planned rather than reactive.

## Current limitation

Current architecture (single VPS, Postgres+pgvector, no caching, no connectors) is sized for controlled-pilot scale (`docs/adr/0027-vps-first-controlled-pilot-hosting.md`); no explicit thresholds are defined for when each component needs to change.

## Why postponed

Not postponed in the sense of being unwanted — it's inherently sequenced *after* observability (`docs/adr/0024-observability-before-scaling.md`) because scaling decisions need production evidence, not projection, to be trustworthy.

## Dependencies

- `docs/architecture/observability.md`'s trace/cost/latency data as the evidence source for every scaling trigger.
- `docs/engineering/scaling-strategy.md` (the detailed tier-by-tier breakdown this roadmap references).

## Implementation phases

Mirrors `docs/engineering/scaling-strategy.md`'s tiers: 100 → 1,000 → 10,000 → 100,000 customers, each with its own defined trigger (not a fixed calendar date) for VPS→multi-instance, pgvector→Qdrant (`docs/future/QdrantMigration.md`), Azure activation (`docs/adr/0029`), caching (`docs/future/CachingV2.md`), and connector/ingestion scaling (`docs/future/ContinuousIngestion.md`).

## Technical design

No single technical design — this is a sequencing document referencing the individually-specced scaling items; see `docs/engineering/scaling-strategy.md` for the concrete per-tier detail.

## Evaluation plan

Each scaling step is evaluated independently per its own spec (e.g. `docs/future/QdrantMigration.md`'s evaluation plan) before being executed; this roadmap's own "evaluation" is whether the trigger conditions were actually met before acting.

## Rollback strategy

Deferred to each individual scaling item's own rollback plan; this document's role is sequencing, not execution.

## Success metrics

Every scaling change made in this roadmap is traceable to a specific, met trigger condition — no scaling investment made ahead of evidence.
