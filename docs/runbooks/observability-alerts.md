# Runbook: Observability Alerts

## Symptoms

A structured alert event fires (`docs/architecture/observability.md`'s alert types: p95 latency, provider/embedding error rate, fallback rate, evidence-insufficient rate, invalid citation attempts, guardrail spikes, token/cost spikes, zero traffic).

## Diagnosis

1. Identify which specific alert fired and pull the `GET /observability/alerts` detail.
2. Cross-reference against `GET /observability/anomalies` (deterministic 24h-vs-7-day-baseline comparison) for corroborating signal.
3. Route to the specific matching runbook: `docs/runbooks/high-latency.md`, `docs/runbooks/high-token-cost.md`, `docs/runbooks/llm-provider-outage.md`, `docs/runbooks/prompt-regressions.md`, etc.

## Recovery

Deferred to the specific matching runbook above — this runbook's job is triage/routing, not resolution.

## Validation

The specific alert clears and doesn't re-fire; the underlying matched runbook's validation criteria are met.

## Escalation

If no specific runbook matches the alert pattern, treat as `docs/sops/production-incidents.md`'s general process, and consider whether a new runbook should be written for this pattern.

## Post-incident review

Was the alert threshold well-calibrated (fired appropriately, not too noisy/too late)? Feeds `docs/architecture/observability.md`'s alert-threshold tuning.
