# Observability V2

## Purpose

Address the explicitly-deferred items from the initial AI observability implementation once evidence justifies the added complexity: materialized cost/metrics rollups, `encrypted_full_content` retention, richer alerting delivery, and a fuller Grafana dashboard suite.

## Current limitation

`docs/architecture/observability.md` — cost/metrics aggregation is computed on-read via SQL `GROUP BY` (no rollup table); `encrypted_full_content` retention mode falls back to `redacted_preview` (no KMS integration); alerts are structured log events + read API only (no webhook/email/Slack delivery); only one starter Grafana dashboard exists.

## Why postponed

These were explicitly scoped out of the initial observability build as lightweight-for-now tradeoffs (see the original implementation's "Explicitly deferred" list) rather than oversights — each needs either a scale trigger (rollup tables) or an explicit infrastructure decision (KMS for encryption, an alert-delivery channel choice) that wasn't needed to ship v1.

## Dependencies

- On-read aggregation query latency becoming measurably slow (the trigger for rollup tables).
- A KMS/secrets-management decision (the trigger for `encrypted_full_content`).
- A concrete need for proactive alert delivery beyond the read API (the trigger for webhook/email/Slack).

## Implementation phases

1. Materialized rollup tables for cost/metrics aggregation, once on-read `GROUP BY` performance is measured as a real bottleneck.
2. `encrypted_full_content` retention mode, once a KMS choice is made — encrypts rather than redacts full prompt/response content for tenants requiring it.
3. Alert delivery (webhook/email/Slack) once a specific delivery channel is requested/required.
4. Expanded Grafana dashboard suite as operational experience reveals which views are actually used.

## Technical design

Each item is additive to the existing trace model/API — no breaking change to `ai_traces`/`ai_trace_stages`/`ai_retrieval_traces`/`ai_model_call_traces`/`ai_guardrail_traces` is required for any of these.

## Evaluation plan

Rollup tables: verify aggregate query results match the existing on-read computation exactly before switching reads over. Encryption: verify decrypt-on-read RBAC matches today's `include_content=true` stricter-role gate exactly.

## Rollback strategy

Rollup tables can be dropped and reads reverted to on-read aggregation with no data loss (rollups are derived, not source-of-truth). Alert delivery channels are independently disableable per channel.

## Success metrics

Faster dashboard/API response times (if rollups are built), successful encrypted-content retention for tenants requiring it, and reduced time-to-notice for alert-worthy events (if delivery is built).
