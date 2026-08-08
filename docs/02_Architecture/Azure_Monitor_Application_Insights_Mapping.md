# Azure Monitor / Application Insights Mapping

Status: reference document - this platform currently deploys to a low-cost VPS (see ADR `0018-controlled-pilot-production-hosting-and-observability-model`); this document maps today's implementation onto Azure Monitor for a future migration, and is not itself a deployment guide.

## Why this mapping matters

The observability implementation (`AI_Observability_Architecture.md`) was built to remain Azure-compatible even though the first production deployment target is a VPS: it reuses OpenTelemetry concepts throughout, and the existing Azure Monitor OTel Distro integration (`configure_azure_monitor`, unchanged by this work) continues to take precedence whenever it's configured (see `OpenTelemetry_Setup_Guide.md`'s precedence rules). This document is the map for whoever picks up an eventual Azure migration.

## Component mapping

| VPS-tier component | Azure equivalent | Notes |
|---|---|---|
| OTel Collector (`docker-compose.observability.yml`) | Not needed - Azure Monitor OTel Distro exports directly to Application Insights, no collector hop required. | Set `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=true` + `APPLICATIONINSIGHTS_CONNECTION_STRING`; `OTEL_ENABLED` is then ignored (Azure wins per the precedence rule). |
| Prometheus | Azure Monitor Metrics / Log Analytics metrics. | Application Insights already captures request/dependency metrics; a dedicated Prometheus instance is not typically needed on Azure. |
| Tempo (distributed traces) | Application Insights end-to-end transaction view. | `otel_trace_id`/`otel_span_id` on `ai_traces` remain the join key either way - only the backend they point into changes. |
| Loki (log search) | Log Analytics workspace (KQL). | Existing query pack: `infrastructure/azure/monitoring/queries/*.kql`, notably `request-id-correlation.kql`. |
| Grafana | Azure Monitor Workbooks. | Existing template: `infrastructure/azure/monitoring/workbooks/controlled-pilot-observability.workbook.json`. A new workbook panel set covering the AI-specific metrics in `AI_Metrics_Dictionary.md` would be the direct port of `conversa-api-overview.json`. |
| `app.observability.alerts` (structured JSON events) | Azure Monitor scheduled query alerts + action groups. | `deployment/widget/alerts.json` is already the provider-neutral alert source used by the existing Azure alerting setup (see `Azure_Observability_Telemetry_and_Alerts.md`) - the new AI-specific thresholds in `AI_Alert_Threshold_Guide.md` would extend that same pattern rather than introducing a second alerting mechanism. |
| `ai_traces` + friends (Postgres tables) | Unchanged - these are application data, not infrastructure telemetry, and migrate with the rest of the database regardless of which cloud/VPS the API runs on. | This is the one piece of this feature that is *not* Azure/VPS-specific at all. |

## What does NOT change on an Azure migration

- The 5-table AI trace data model, the recording layer (`AITraceRecorder`), the RAG orchestrator wiring, the redaction service, the retention job, and the `/observability` API/UI are all infrastructure-agnostic - they read/write Postgres and don't know or care which cloud (if any) the process runs on.
- RBAC, tenant isolation, and the privacy/retention model are unchanged.

## What DOES change

- Set `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=true` and `APPLICATIONINSIGHTS_CONNECTION_STRING` (already-existing config, see `Azure_Observability_Telemetry_and_Alerts.md`) instead of `OTEL_ENABLED`/`OTEL_EXPORTER_OTLP_ENDPOINT`.
- Retire `docker-compose.observability.yml` (or simply never deploy it) - its job is fully absorbed by Application Insights + Log Analytics.
- Point dashboards at the Azure Monitor Workbook instead of Grafana; port `conversa-api-overview.json`'s panel definitions into KQL queries in the existing workbook.
- Alert delivery moves from "structured log line, read via API" to Azure Monitor action groups (email/webhook), following the same severity mapping already documented in `Azure_Observability_Telemetry_and_Alerts.md` (critical → Sev1, warning → Sev3).

## Non-goals of this mapping

This document does not itself perform a migration, provision Azure resources, or change any code. It exists so that when a real Azure migration is planned, the "what maps to what" research is already done rather than needing to be re-derived from scratch.
