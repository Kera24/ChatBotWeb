# Runbook: Connector Failures

Applies once `docs/future/ConnectorFramework.md` is implemented.

## Symptoms

A connector's scheduled sync fails, produces incomplete ingestion, or a tenant reports stale/missing content from a connected source.

## Diagnosis

1. Check connector sync status/history (tenant-visible, per `docs/future/ContinuousIngestion.md`'s design) for the specific failure.
2. Distinguish: external-API-side failure (auth expired, rate-limited, source unavailable) vs. Conversa-side bug in the connector's sync logic.
3. Confirm the failure didn't corrupt or block the manual-upload path for the same tenant (`docs/checklists/connector-checklist.md`'s invariant).

## Recovery

1. External-API-side: often self-resolving (retry with backoff); if auth expired, tenant needs to re-authorize.
2. Conversa-side bug: use the per-connector kill switch to stop further damage, fix following the standard lifecycle, re-enable.
3. Re-sync affected content once the underlying issue is resolved — verify checksums correctly detect what actually changed vs. re-ingesting everything.

## Validation

Sync resumes successfully; tenant's content is current; no impact confirmed on the manual-upload path or other tenants' connectors.

## Escalation

Recurring failures for a specific connector type escalate to a review of that connector's implementation quality, not just repeated manual fixes.

## Post-incident review

Was the tenant-visible sync status clear enough that they didn't need to file a support ticket to discover the problem? Feeds the connector framework's monitoring design.
