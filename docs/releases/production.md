# Release Type: Production

For general availability to all tenants.

## Entry criteria

Every gate in `docs/production/readiness-gates.md` satisfied: tests, evaluation thresholds, regression checks, guardrails, observability, documentation, rollback plan, performance, security, deployment validation, customer readiness.

## Exit criteria

Deployed, smoke-checked, and monitored through the standard post-deploy window (`docs/checklists/production-checklist.md`) with no attributable anomaly.

## Evaluation requirements

Full deterministic evaluation gate passes with unchanged thresholds (`docs/adr/0025-deterministic-evaluation-gates.md`) — no exceptions.

## Rollback

`docs/sops/rollback.md`, with a rollback plan identified and understood **before** deployment, not improvised after an issue.

## Monitoring

Standard post-deploy monitoring window per `docs/checklists/production-checklist.md`, proportional to change risk/blast radius.

## Approval requirements

Human review (`docs/workflows/engineering-lifecycle.md` stage 15) plus explicit release approval (stage 16) confirming every readiness gate — no informal overrides.
