# Observability — Current / Future / Out of Scope

## Current

Per-request AI trace model (`ai_traces` + 4 child tables), 14-stage pipeline instrumentation, redaction-by-default, dual-path OTel (Azure Monitor or generic OTLP), optional VPS metrics stack (`docker-compose.observability.yml`), RBAC-scoped observability API + minimal dashboard/trace-detail UI, deterministic (non-ML) anomaly/drift signals. Full detail: `docs/03_AI/AI_Observability_Architecture.md` and `docs/architecture/observability.md`. Decision record: ADR 0024 (observability before scaling).

## Future

- `encrypted_full_content` retention mode (needs a KMS decision) — currently falls back to `redacted_preview`.
- Materialized cost/metrics rollup tables once on-read `GROUP BY` aggregation stops being fast enough at scale — see `docs/future/ObservabilityV2.md`.
- Webhook/email/Slack alert delivery beyond the current structured-log-event + read-API model.

## Out of scope (not planned)

- ML-based anomaly detection — anomaly/drift signals stay deterministic threshold comparisons unless explicitly revisited (see ADR 0024's reconsideration triggers).
