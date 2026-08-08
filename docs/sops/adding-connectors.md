# SOP: Adding Connectors

## Purpose

Add a new automated knowledge-source connector, per `docs/connectors/connector-framework.md` and `docs/future/ConnectorFramework.md`.

## When to use

Confirmed tenant demand for a specific external source (Notion, Confluence, Google Drive, etc.) — never built speculatively (`docs/adr/0026-manual-ingestion-before-connectors.md`).

## Step-by-step process

1. Confirm the demand signal (support/sales feedback), per `docs/priorities/priority-matrix.md`'s categorization of the specific connector.
2. Implement the connector following `docs/connectors/connector-framework.md`'s lifecycle/auth/permissions/sync/scheduling pattern.
3. Connector output must produce uploads through the existing `create_uploaded_document_with_version()` path — reuse `document_lifecycle` transitions unchanged, never a parallel ingestion route.
4. Implement rate limiting/backoff/retry against the external API's own limits.
5. Add a per-connector kill switch.
6. Test end-to-end: full sync, partial failure, full failure, re-sync after fix.

## Validation

`docs/checklists/connector-checklist.md` in full.

## Rollback

Per-connector kill switch (disable sync; already-ingested documents remain queryable and unaffected).

## Success criteria

Connector-sourced documents behave identically to manual uploads in every downstream system (evaluation, citations, guardrails); sync failures never corrupt or block the manual-upload path.
