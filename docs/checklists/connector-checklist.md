# Connector Checklist

Applies once `docs/future/ConnectorFramework.md` is implemented — see `docs/connectors/connector-framework.md` for the full architecture this checklist verifies against.

## Required validation

- Connector-sourced documents pass through the exact same `document_lifecycle` transitions, chunking, and embedding pipeline as manually uploaded documents — verified by test, not assumption.
- Sync failure handling tested (partial failure, full failure, retry behavior).

## Things to verify

- Per-tenant credential storage for the external system follows existing secret-handling patterns (never plaintext, never logged).
- Checksum-based dedup is reused, not reinvented, for change detection.
- Sync scheduling doesn't bypass rate limits on the external API (self-imposed backoff, not just relying on the external service to reject).
- A connector failure never blocks or corrupts the manual-upload path for the same tenant.
- Per-connector kill switch exists and is tested.

## Common mistakes

- Building a parallel ingestion pipeline instead of feeding into the existing `document_lifecycle`.
- Storing external-system credentials without going through the existing secret-handling conventions.
- No backoff/retry strategy, causing the connector to be rate-limited or banned by the external API.

## Required documentation

- New connector's specifics documented in `docs/connectors/connector-roadmap.md`'s per-connector notes once built.

## Definition of Done

Connector-sourced documents indistinguishable from manual uploads in downstream lifecycle behavior; credentials handled securely; kill switch tested; no impact on manual-upload path from a connector failure.
