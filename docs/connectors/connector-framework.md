# Connector Development Framework

The future architecture for automated knowledge-source connectors. This document specifies the framework itself; `docs/connectors/connector-roadmap.md` lists and prioritizes individual connectors; `docs/future/ConnectorFramework.md` and `docs/future/ContinuousIngestion.md` are the postponed-feature specs this framework will implement; `docs/sops/adding-connectors.md` and `docs/checklists/connector-checklist.md` are the operational procedures once it exists. **Nothing in this document is implemented today** — manual upload is the only ingestion path currently (`docs/engineering/knowledge-ingestion.md`), per `docs/adr/0026-manual-ingestion-before-connectors.md`.

## Connector lifecycle

Mirrors `document_lifecycle`'s explicit-transition philosophy: `disconnected → authorizing → connected → syncing → synced` (or `sync_failed`), with `paused`/`disabled` as tenant- or system-initiated states. A connector never silently transitions — every state change is auditable, matching the existing `document_lifecycle` and `conversation_lifecycle` precedent.

## Authentication

Per-tenant OAuth2 (for M365/Google Workspace/Slack/Notion-style sources) or API-key (for REST/database sources), stored via the existing secret-handling conventions (`docs/engineering/security.md`) — never plaintext, never logged, never returned in any API response body. Token refresh handled automatically; expired/revoked auth transitions the connector to a tenant-visible "needs reauthorization" state rather than failing silently.

## Permissions

A connector requests the minimum external-system scope needed for read-only content access — never write access to the external system, and never broader scope than the specific source being connected (e.g. one SharePoint site, not "all of Microsoft 365"). Tenant admin (`org_owner`/`client_admin`, matching existing RBAC tiers) is the only role that can configure a connector.

## Incremental sync

Reuses the existing checksum-based dedup (`docs/architecture/knowledge-ingestion.md`) for change detection — a poll only re-ingests content whose checksum changed, never a full re-ingest by default. Deletions at the source propagate to a `Document` archival transition, not a hard delete, matching existing lifecycle conventions.

## Scheduling

Per-connector configurable poll interval (tenant-configurable within system-enforced min/max bounds to protect the external API and Conversa's own ingestion capacity). A scheduled job (cron-style — no new heavyweight job-queue infrastructure unless connector volume demands it, per `docs/future/ContinuousIngestion.md`) invokes each active connector's poll method.

## Rate limiting

Self-imposed backoff against the external API's documented limits — never relying on the external service to reject requests as the only throttle. Exponential backoff on 429/5xx responses from the source system.

## Retries

Transient failures (network blip, momentary rate limit) retry automatically with backoff; persistent failures (auth expired, source deleted, permission revoked) surface as a tenant-visible connector status, not a silent retry loop.

## Monitoring

Connector sync status/history is traced the same way RAG requests are (`docs/architecture/observability.md`'s instrumentation pattern) — sync attempts, success/failure, documents affected, latency — surfaced via `/observability` and a connector-specific status view in the dashboard.

## Testing

Every connector implementation is tested against: full sync, incremental sync (only-changed-content), partial failure (some documents fail, others succeed), full failure (source unreachable), and re-sync-after-fix. Connector-sourced documents are tested through the *exact same* downstream evaluation/guardrail/citation path as manual uploads — no special-casing.

## Deployment

A new connector ships behind a per-tenant enablement flag; first tenant enablement is treated as a beta-tier rollout (`docs/releases/beta.md`) regardless of how many other connectors already exist, since each connector is a genuinely new integration surface.

## Connector onboarding standards

Before a new connector type is built (not just configured for an existing type):

1. Confirmed tenant demand (`docs/adr/0026-manual-ingestion-before-connectors.md`'s evidence-based standard) — never built speculatively.
2. A named owner responsible for the specific external API's quirks/rate limits/auth model.
3. A test tenant/sandbox account with the external system, used for the full test matrix above before any real tenant is onboarded.
4. Documentation of the connector's specific scope/permission model added to `docs/connectors/connector-roadmap.md`.
5. `docs/checklists/connector-checklist.md` passed in full before the per-tenant enablement flag is turned on for any real tenant.
