# Continuous Ingestion

## Purpose

Keep tenant knowledge current automatically (scheduled re-sync/re-processing) instead of requiring a manual re-upload every time source content changes.

## Current limitation

Ingestion is a one-shot event per upload (`docs/architecture/knowledge-ingestion.md`); a document that changes at its source has no mechanism to update automatically.

## Why postponed

Depends on `docs/future/ConnectorFramework.md` shipping first — continuous ingestion is meaningless without an automated source to sync from; manual-upload tenants have no "continuous" source to poll.

## Dependencies

- `docs/future/ConnectorFramework.md` (connectors provide the sync mechanism this builds on).
- Change-detection (checksum comparison, already used for upload dedup — `docs/architecture/knowledge-ingestion.md`) extended to a scheduled-poll context.

## Implementation phases

1. Add a scheduling layer to the connector framework (poll interval per connector/tenant).
2. On each poll, diff source content against the last-known checksum; only re-process changed content.
3. New content creates a new `DocumentVersion` through the existing lifecycle, not a mutation of history.
4. Add tenant-visible sync status/history so a failed or stale sync is discoverable, not silent.

## Technical design

A scheduled job (cron-style, VPS-appropriate — no new heavyweight job-queue infrastructure unless connector volume demands it) invoking each active connector's poll method; reuses `document_lifecycle` transitions for the resulting version.

## Evaluation plan

Verify re-processed/updated documents flow through the same evaluation and citation-scope guarantees as any other version transition; monitor for sync-triggered evaluation regressions.

## Rollback strategy

Per-connector/tenant sync can be paused without affecting already-ingested content; a bad sync's resulting document version can be rolled back to the prior active version via the existing lifecycle (`Document.active_document_version_id`).

## Success metrics

Reduced staleness (time between source change and knowledge-base update) for connector-sourced tenants, with no increase in ingestion error rate.
