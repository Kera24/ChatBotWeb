# Connector Framework

## Purpose

Allow tenants to ingest knowledge automatically from external systems (Notion, Confluence, Google Drive, website crawl) instead of only manual upload.

## Current limitation

`docs/architecture/knowledge-ingestion.md` supports only manual upload; a tenant whose knowledge lives entirely in an external system gets no ingestion path without exporting/uploading manually.

## Why postponed

`docs/adr/0026-manual-ingestion-before-connectors.md` — the ingestion pipeline (lifecycle, chunking, embedding) needed to be proven correct against manual upload first, since connectors would build on top of it, not replace it.

## Dependencies

- Stable manual-upload ingestion pipeline in production (`docs/architecture/knowledge-ingestion.md`).
- Per-tenant credential storage for external-system auth (extends the existing `PublicCredential`-style secret-handling patterns, `docs/engineering/security.md`).
- Sustained tenant demand signal (support/sales feedback), per `docs/adr/0026`'s reconsideration trigger.

## Implementation phases

1. Define a `Connector` abstraction (source type, auth config, sync schedule) that produces the same `Document`/`DocumentVersion` shapes manual upload does.
2. Build the first connector (highest-demand source) end-to-end, reusing `document_lifecycle` transitions unchanged.
3. Add sync scheduling and change detection (checksum-based dedup already exists and should be reused, not reinvented).
4. Add a second connector once the abstraction is proven not to be over-fit to the first.

## Technical design

New `app.services.connectors.*` package; each connector implementation produces uploads through the existing `create_uploaded_document_with_version()` path rather than a parallel ingestion route — connectors are a new *source*, not a new *pipeline*.

## Evaluation plan

Verify connector-sourced documents pass through identical lifecycle/chunking/embedding/evaluation paths as manual uploads with no special-casing; monitor sync failure rates via observability.

## Rollback strategy

Per-connector kill switch (disable sync, existing ingested documents remain queryable); connector failures must never block or corrupt the manual-upload path.

## Success metrics

Tenant adoption of at least one connector post-launch; sync success rate; no regression in ingestion pipeline reliability for manual uploads.
