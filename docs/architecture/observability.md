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

## Full telemetry architecture (production monitoring stack)

Everything above this section is the **product's own** observability (Postgres-backed AI traces, the in-app `/observability` dashboard, `app.observability.alerts`, `app.alerting`'s proactive delivery). This section covers the **optional, self-hostable operational monitoring stack** that sits alongside it:

```
Conversa (FastAPI + Python logging)
  -> OpenTelemetry SDK (app.operations.telemetry)
      - traces: TracerProvider, FastAPIInstrumentor + SQLAlchemyInstrumentor + telemetry_span()
      - metrics: MeterProvider, FastAPIInstrumentor's http.server.* + app.observability.otel_metrics
      - logs: LoggerProvider, a LoggingHandler bridging the root Python logger
  -> OTLP/HTTP (deployment/observability/otel-collector-config.yaml)
  -> OTel Collector
      - traces -> Tempo (deployment/observability/tempo.yaml)
      - metrics -> Prometheus (via the collector's own prometheus exporter, scraped by deployment/observability/prometheus.yml)
      - logs -> Loki (deployment/observability/loki-config.yaml)
  -> Grafana (deployment/observability/grafana-provisioning/*)
      - dashboards: Conversa API Overview, Conversa AI Observability, Conversa Platform Health
      - alerting: deployment/observability/grafana-provisioning/alerting/rules.yaml
```

Brought up with `docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml --env-file .env.production up -d` and `OTEL_ENABLED=true` / `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318` — see `docs/06_Operations/Grafana_Prometheus_Loki_Tempo_VPS_Guide.md` for the full setup/retention/resource-budget reference. Entirely optional: the minimum tier (structured JSON stdout logs + Postgres AI traces + `/health/live`/`/health/ready` + `deployment/monitoring/check.sh`) runs the product fully without any of this.

**Vendor-neutral by construction**: every signal leaves the process as standard OTLP over `app.operations.telemetry`'s generic OTel SDK path (the Azure Monitor path, `configure_azure_monitor`, is a separate, mutually-exclusive precedence branch — only one can be active). Pointing `OTEL_EXPORTER_OTLP_ENDPOINT` at a different OTLP-compatible backend (Azure Monitor's OTel-native ingestion, Datadog, Honeycomb, New Relic, or an enterprise customer's own collector) requires no application code change — see "Future managed-backend portability" below.

**What reuses what**: the collector/Prometheus/Loki/Tempo/Grafana deployment files, the "Conversa API Overview" dashboard, and the Azure Monitor precedence logic all predate this pass and are unchanged in shape. What was added: (1) the metrics half of `_configure_generic_otel` (a `MeterProvider` was never registered before, so `FastAPIInstrumentor`'s `http.server.*` metrics — which the existing dashboard already queried — had no data; same gap for `OTEL_EXPORTER_OTLP_ENDPOINT`'s per-signal path, which was passed unsuffixed to `endpoint=` and would have 404'd against the collector's `/v1/traces`/`/v1/metrics` receivers), (2) the logs half (a `LoggerProvider` + root-logger bridging handler, closing the "no log shipping into Loki" gap the VPS guide previously documented as out of scope), (3) `app.observability.otel_metrics` and its call sites, (4) two new Grafana dashboards and a provisioned alert-rule set, (5) explicit datasource `uid:`s (the dashboard JSON already referenced literal UIDs like `"Prometheus"` that were never actually assigned in `datasources.yaml`).

## Cardinality policy

**Prometheus labels must stay low-cardinality.** Every metric in `app.observability.otel_metrics` and every label FastAPIInstrumentor's own `http.server.*` metrics attach is drawn from a small, closed vocabulary: `service`/`environment` (resource attributes, one value per deployment), `route` (the *normalised* route template from `app.operations.telemetry.normalise_route` — e.g. `/api/v1/widget/{public_key}/messages`, never a raw path containing an id), `provider`/`model` (a handful of configured AI providers/models), `stage` (the fixed `STAGE_*` vocabulary in `app.observability.context`, 14 values), `status`/`outcome`/`verdict`/`answer_state`/`result` (small enums), `layer`/`guardrail` (guardrail layers A-H, a fixed set), `email_type`/`error_code` (fixed enums).

**Never attach as a Prometheus label**: `organisation_id`, `workspace_id`, `assistant_id`, `conversation_id`, `request_id`, `user_id`, `prompt_version`, `experiment_id`, or any other per-tenant/per-request identifier. Each of these is unbounded (grows with customer count or request volume) and would blow up Prometheus's time-series cardinality — the classic "high-cardinality label" failure mode that degrades or crashes a Prometheus instance. `tests/test_otel_metrics.py::test_no_high_cardinality_labels_are_ever_attached` asserts this holds for every `otel_metrics.record_*` function.

**Where the high-cardinality data actually lives**: organisation_id/workspace_id/assistant_id/request_id/trace_id/prompt_version/experiment_id are all still fully available — just in the systems built for high-cardinality, per-request lookup instead of aggregate metrics: Postgres `ai_traces`/`ai_model_call_traces` (queried via `/observability`), Tempo (trace_id-keyed spans, correlated to Loki via the `Tempo` datasource's `tracesToLogsV2` provisioning), and Loki (log lines already carry whatever structured fields `log_operational_event` put in them, searchable by any field via LogQL). A Prometheus counter answers "is the AI provider failure rate elevated right now" in O(1) regardless of tenant count; a Tempo/Loki/Postgres query answers "which specific request, for which tenant, failed and why."

**Adding a new metric**: before adding a label, ask whether its value set is bounded and small (a handful of enum-like values) regardless of how many customers or requests exist. If not, it belongs in a trace/log attribute, not a metric label.

## Alert responsibility split

Two independent, complementary systems evaluate different things:

| | **`app.alerting`** (built earlier, unchanged by this pass) | **Grafana alerting** (new, `deployment/observability/grafana-provisioning/alerting/rules.yaml`) |
|---|---|---|
| Evaluates | `app.observability.alerts.evaluate_alerts`'s per-tenant thresholds (via the `alert_dispatch_run` CLI), plus evaluation/release-gate verdicts (`app.alerting.hooks.notify_gate_failure`) | Cardinality-safe Prometheus aggregates across the whole deployment — no tenant dimension exists in these metrics at all |
| Delivery | Email (`EmailAlertProvider`, reuses the transactional email abstraction), Slack webhook, dev (log-only) — `app.alerting.dependencies.build_alert_provider` | Grafana's own contact points/notification policies (email/Slack/PagerDuty/webhook/etc. — not provisioned here, see the VPS guide) |
| Dedup/cooldown | `app.alerting.cooldown.AlertCooldownStore` (file-based, per alert_key/tenant scope) | Grafana's native alert grouping, silencing, and `for:` sustained-condition duration |
| Scope | Application-specific critical events: evaluation gate failures, release-gate failures — the immediate, "this specific tenant/run needs attention now" notification | Production infrastructure/service/model monitoring: elevated 5xx, AI provider failure rate, sustained latency degradation, cost spikes, evaluation regressions (aggregate view), collector/service unavailability, no-traffic/telemetry-missing |
| Role | Immediate notification path + development/fallback (works with zero infrastructure beyond the API itself — `dev` provider is the safe default) | The scalable, aggregate, "SRE dashboard + on-call paging" source of truth once the recommended-tier stack is deployed |

Both are intentionally kept: `app.alerting` was never replaced or weakened by this work, and the two systems' overlap (e.g. both surface an AI provider failure rate) is deliberate defense-in-depth, not duplicated logic — Grafana's rules independently query the same underlying `otel_metrics` counters `app.alerting`'s CLI never touches, and neither reads the other's state.

## Investigation workflow

1. **Notice**: a Grafana alert fires (aggregate, deployment-wide), an `app.alerting` email/Slack notification arrives (tenant-specific, evaluation/release-gate), or a customer reports an issue.
2. **Confirm scope**: check the relevant Grafana dashboard (Conversa API Overview / AI Observability / Platform Health) for the affected metric's trend and whether it's isolated or deployment-wide.
3. **Narrow to a request or tenant**: if the issue is tenant-specific, use the in-app `/observability` dashboard (Postgres-backed, has organisation/workspace/assistant filters the Prometheus layer deliberately never gets) to find the specific failing trace(s).
4. **Cross-reference traces and logs**: open the trace in Tempo (via Grafana, or the in-app trace detail view's `otel_trace_id` if AI_TRACE_ENABLED) and jump to correlated Loki logs (the Tempo datasource is provisioned with `tracesToLogsV2` for exactly this).
5. **Root-cause at the stage level**: the trace's per-stage breakdown (embedding/retrieval/generation/guardrails/...) identifies which pipeline stage and, for AI calls, which provider/model/prompt version was involved — see `docs/operations/observability-workflow.md`'s full loop (Telemetry -> Dashboards -> Alerts -> Incident Detection -> Root Cause Analysis -> Golden Dataset Update -> Regression Testing -> Redeployment).
6. **Escalate/route**: `docs/runbooks/observability-alerts.md` routes to the specific matching runbook (`high-latency.md`, `high-token-cost.md`, `llm-provider-outage.md`, `prompt-regressions.md`, etc.).

## Customer vs internal observability

Three distinct layers, deliberately kept separate:

1. **Internal operator observability** (this document's subject): the full Grafana stack — infrastructure, service, and AI-provider-level metrics/logs/traces across every tenant in aggregate. Grafana is published only on `127.0.0.1` on the VPS (SSH tunnel or an authenticated Caddy route required) — never exposed to customers, and its metrics carry no tenant-identifying labels even if it were (see the cardinality policy above — this is defense-in-depth, not the only control).
2. **Customer analytics**: the existing, already-safe business/product metrics surfaced inside Conversa itself — the in-app `/observability` dashboard (scoped to the customer's own organisation/workspace via normal RBAC, `require_organisation_role`), evaluation results, and billing/usage views. This is a completely separate code path from the Grafana stack; nothing here changed it.
3. **Future enterprise telemetry export** (not implemented): a hypothetical customer-owned OTLP/SIEM/Datadog/Azure Monitor integration, so an enterprise customer could receive their own tenant's traces/logs in their own observability tooling. No such export exists today, and none should be built speculatively — if this becomes a real requirement, the natural extension point is a second OTLP export target scoped and filtered per-tenant before it leaves the process (a materially different problem from the deployment-wide collector export this document describes, since it requires tenant-aware filtering that the current cardinality-safe metrics pipeline deliberately does not do). See `docs/future/EnterpriseRoadmap.md` / `docs/future/ComplianceRoadmap.md` for the existing forward-looking specs this would extend.

## Future managed-backend portability

Because every signal already leaves the process as standard OTLP (see "Full telemetry architecture" above), migrating off the self-hosted Prometheus/Loki/Tempo/Grafana stack to a managed backend is a configuration change, not a code change:

- **Azure Monitor**: already supported today via the mutually-exclusive `configure_azure_monitor` precedence branch (`AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=true` + `APPLICATIONINSIGHTS_CONNECTION_STRING`) — see `docs/architecture/deployment.md` and ADR-0029 (retain Azure architecture without deploying).
- **Datadog / Honeycomb / New Relic / any OTLP-compatible vendor**: point `OTEL_EXPORTER_OTLP_ENDPOINT` at the vendor's OTLP ingestion endpoint (directly, or via their own collector) instead of the self-hosted `otel-collector` service — `app.operations.telemetry`'s generic OTel path already emits standard OTLP for traces, metrics, and logs, with no vendor-specific SDK code anywhere in the application layer.
- **What would need attention on migration**: the collector's redaction processor (`attributes/redact_secrets` in `otel-collector-config.yaml`) and the app-level redaction it backstops (`app.observability.redaction`, `app.operations.logging.redact`) travel with the OTLP stream regardless of backend, since redaction happens before export — a vendor migration does not reopen the security posture described below. Dashboards and alert rules, however, are backend-specific (Grafana JSON/YAML here) and would need re-authoring in the new backend's own format.
