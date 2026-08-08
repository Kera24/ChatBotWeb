# Production Checklist

## Required validation

- Post-deployment smoke checks pass.
- Monitoring window (proportional to change risk) shows no attributable anomaly.

## Things to verify

- Dashboards (`/observability`) show the deployed change's traces flowing correctly.
- No alert threshold breached (`docs/architecture/observability.md`'s alert types: p95 latency, error rate, fallback rate, evidence-insufficient rate, guardrail spikes, cost spikes, zero traffic).
- Backup/restore still functions (verified periodically, not just at deploy time — `deployment/backup/`).
- On-call/escalation path is clear for the deployed change (who gets paged if it breaks).

## Common mistakes

- Declaring "production ready" without an actual monitoring window post-deploy.
- Not knowing which runbook (`docs/runbooks/`) applies if this specific change breaks.

## Required documentation

- Any anomaly observed gets a post-incident note per the applicable `docs/runbooks/*.md`.

## Definition of Done

Smoke checks pass; monitoring window clean; escalation path known; backup/restore verified within its normal cadence.
