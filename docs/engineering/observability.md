# Observability — Current / Future / Out of Scope

## Current

Per-request AI trace model (`ai_traces` + 4 child tables), 14-stage pipeline instrumentation, redaction-by-default, dual-path OTel (Azure Monitor or generic OTLP - traces, metrics, and logs, the latter two newly wired), optional VPS metrics stack (`docker-compose.observability.yml`: OTel Collector, Prometheus, Loki, Tempo, Grafana with three provisioned dashboards and a provisioned aggregate alert-rule set), RBAC-scoped observability API + minimal dashboard/trace-detail UI, deterministic (non-ML) anomaly/drift signals, proactive per-tenant alert delivery (`app.alerting`: email via the transactional email abstraction, Slack webhook, dev/log-only) with cooldown/deduplication. Full detail: `docs/03_AI/AI_Observability_Architecture.md` and `docs/architecture/observability.md`. Decision record: ADR 0024 (observability before scaling).

## Future

- `encrypted_full_content` retention mode (needs a KMS decision) — currently falls back to `redacted_preview`.
- Materialized cost/metrics rollup tables once on-read `GROUP BY` aggregation stops being fast enough at scale — see `docs/future/ObservabilityV2.md`.
- Additional `app.alerting` providers beyond email/Slack (Microsoft Teams, Discord, PagerDuty, Opsgenie - the `AlertProvider` abstraction already supports adding one without further redesign).
- A pre-configured Grafana contact point/notification policy - none is provisioned today (no real destination exists to configure safely without inventing one); see `docs/06_Operations/Grafana_Prometheus_Loki_Tempo_VPS_Guide.md`.
- Customer-owned enterprise telemetry export (OTLP/SIEM/Datadog/Azure Monitor per-tenant) - not implemented; see `docs/architecture/observability.md`'s "Customer vs internal observability" section for why this is a materially different (tenant-filtered) problem from the current deployment-wide export.

## Out of scope (not planned)

- ML-based anomaly detection — anomaly/drift signals stay deterministic threshold comparisons unless explicitly revisited (see ADR 0024's reconsideration triggers).
