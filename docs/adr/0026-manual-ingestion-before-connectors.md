# ADR-0026: Manual Ingestion Before Connectors

Status: Accepted
Date: 2026-08-07

## Context

Knowledge can enter the platform either via manual upload (a tenant explicitly uploads a file) or via connectors that pull content automatically from external systems (Notion, Confluence, Google Drive, a website crawl). Connectors are significantly more complex: they require per-source auth, sync scheduling, change detection, and error handling for partial/failed syncs.

## Decision

Ship and stabilize manual document upload/lifecycle (`docs/architecture/knowledge-ingestion.md`) before building any connector framework.

## Alternatives

- **Build a generic connector framework first** — rejected: without a stable, well-tested ingestion pipeline (extract → chunk → embed → activate) proven correct against manually uploaded content, a connector framework would be layering automation complexity on top of an unproven foundation. Manual upload is also strictly simpler to debug when something goes wrong (a human chose to upload this exact file, at this exact time).
- **Build both simultaneously** — rejected: connectors depend on the same lifecycle/chunking/embedding pipeline manual upload uses; building them in parallel risks the pipeline changing shape under two different sets of requirements at once.

## Tradeoffs

- Gains: the ingestion pipeline that connectors will eventually feed into is already proven correct (checksummed dedup, explicit lifecycle transitions, dialect-safe vector writes) before any connector-specific complexity is added on top.
- Costs: tenants without a manual-upload workflow they're willing to use (e.g. teams whose knowledge lives entirely in Notion) get no value until connectors ship.

## Consequences

- `docs/future/ConnectorFramework.md` and `docs/future/ContinuousIngestion.md` are explicitly designed to plug into the existing `document_lifecycle`/chunking/embedding pipeline rather than replace it.
- Any connector work must not bypass `app.services.document_lifecycle`'s transition map — the same rule that applies to manual upload applies to connector-sourced documents.

## Future reconsideration triggers

Sustained tenant demand for a specific connector (evidenced by support/sales feedback, not assumption) once manual ingestion is stable in production — see `docs/roadmap/roadmap.md`.
