# AI Observability Architecture (Summary)

Full detail lives in `docs/03_AI/` — this page is a short orientation pointer, not a duplicate. Read the linked docs before working in this area.

| Question | Doc |
|---|---|
| How does the whole system fit together? | `docs/03_AI/AI_Observability_Architecture.md` |
| What's captured, redacted, and retained, and who can see it? | `docs/03_AI/AI_Trace_Data_and_Privacy_Policy.md` + `docs/03_AI/AI_Trace_Retention_and_Redaction_Guide.md` |
| OpenTelemetry setup (Azure vs. generic OTLP)? | `docs/04_Engineering/OpenTelemetry_Setup_Guide.md` |
| Self-hosted VPS stack (Grafana/Prometheus/Loki/Tempo)? | `docs/06_Operations/Grafana_Prometheus_Loki_Tempo_VPS_Guide.md` |
| What does each dashboard metric mean? | `docs/03_AI/AI_Metrics_Dictionary.md` |
| Alert thresholds? | `docs/06_Operations/AI_Alert_Threshold_Guide.md` |
| How do I read a trace to debug an incident? | `docs/06_Operations/AI_Incident_Investigation_Runbook.md` + `docs/03_AI/Retrieval_Debugger_Guide.md` |
| Future Azure migration mapping? | `docs/02_Architecture/Azure_Monitor_Application_Insights_Mapping.md` |

## One-paragraph summary

Every AI request (dashboard test, public widget, evaluation case) is traced end-to-end through 14 pipeline stages into 5 Postgres tables (`ai_traces` + 4 child tables), via a fail-safe recorder (`app.observability.ai_trace_recorder`) that can never break the request it's observing. Correlation uses explicit parameter threading (`AITraceContext`), not `contextvars`, because the evaluation engine runs RAG calls on a thread pool. Content is redacted and metadata-only by default (`app.observability.redaction`). Exposed via `/observability` (dashboard) and `/observability/traces/{traceId}` (detail), RBAC-gated the same way as the rest of the dashboard.

## Known limitation

AI trace recording is intentionally a no-op for evaluation runs specifically when the database dialect is SQLite (a real cross-thread contention issue was found and mitigated this way — see the Architecture doc's Limitations section). Postgres (production) and all other request paths are unaffected.

## If extending this area

Read `docs/03_AI/AI_Observability_Architecture.md` in full first — it documents the exact reasoning behind the trace-context design, the fail-safe recorder pattern, and several non-obvious pitfalls (SQLite cross-thread locking, session detachment, CORS-with-cookies across ports in local dev) that will otherwise be rediscovered at cost.
