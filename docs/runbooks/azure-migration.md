# Runbook: Azure Migration

## Symptoms

Not an incident runbook in the usual sense — this is the recovery/execution procedure for activating the retained Azure architecture (`docs/adr/0029-retain-azure-architecture-without-deploying.md`) if/when VPS capacity is exceeded or another trigger fires.

## Diagnosis

Confirm the trigger is real: `docs/engineering/scaling-strategy.md`'s ~100,000-customer tier characteristics, or a specific compliance/reliability requirement that the VPS deployment genuinely cannot meet.

## Recovery (migration execution)

1. Validate `infrastructure/azure/` Bicep IaC is current against the live application (check for drift — it's path-scoped CI-validated but not continuously deployment-tested).
2. Follow `docs/adr/0018-controlled-pilot-production-hosting-and-observability-model.md`'s original architecture and release/rollback model (Front Door, Container Apps, managed Postgres+pgvector, Key Vault, Azure Monitor).
3. Execute as a dual-run cutover (both VPS and Azure serving traffic, gradually shifted), per `docs/future/DeploymentRoadmap.md` — never a hard switch.
4. Migrate data (Postgres dump/restore to Azure Database for PostgreSQL Flexible Server) with explicit verification before cutting read/write traffic over.

## Validation

Synthetic smoke checks pass on Azure; dual-run comparison shows parity; full cutover only after a monitoring window confirms stability.

## Escalation

This is a major, deliberate migration — requires the same Architecture Review/ADR process as any major change (`docs/architecture/evolution-policy.md`), not an ad hoc emergency action, even if triggered by a capacity crisis (which itself indicates the migration should have started earlier).

## Post-incident review

Not applicable as an incident review — instead, this execution becomes its own ADR closing the loop on `docs/adr/0029`'s reconsideration trigger.
