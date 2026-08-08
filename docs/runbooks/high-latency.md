# Runbook: High Latency

## Symptoms

p95/p99 latency alert fired (`docs/architecture/observability.md`'s latency threshold), or user-facing slowness reported.

## Diagnosis

1. Pull recent traces and check `ai_trace_stages` per-stage latency breakdown — is it retrieval, provider call, guardrail processing, or persistence that's slow?
2. Check if it's correlated with a specific tenant/assistant (large knowledge scope, unusual query pattern) or platform-wide.
3. Check Postgres/pgvector query performance directly if retrieval is the slow stage.
4. Check provider-side latency (if the generation call itself is slow, this may be a provider issue — see `docs/runbooks/llm-provider-outage.md`).

## Recovery

1. If a specific slow query pattern is found (e.g. pgvector under load): consider whether `docs/engineering/scaling-strategy.md`'s triggers are being met.
2. If provider-side: no immediate fix available beyond `docs/future/ModelRouting.md`'s fallback (if implemented) — otherwise, wait out the provider issue while monitoring.
3. If correlated with a recent deploy that added pipeline stages: verify the new stage's cost was accounted for (`docs/checklists/performance-checklist.md`); consider rollback if unaccounted-for.

## Validation

p95 latency back under threshold; no ongoing alert.

## Escalation

If latency is sustained and attributable to genuine scale (not a bug), escalate to `docs/engineering/scaling-strategy.md`'s tier-appropriate migration discussion, not a one-off fix.

## Post-incident review

Was the slow stage instrumented well enough to diagnose quickly? If not, that's an observability gap to close (`docs/checklists/observability-checklist.md`).
