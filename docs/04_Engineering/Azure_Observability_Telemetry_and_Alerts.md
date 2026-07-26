# Azure Observability, Telemetry, and Alerts

Status: TASK-068B3 implemented, not live-verified

## Model

Controlled-pilot observability uses Azure Monitor, Log Analytics, and workspace-based Application Insights. FastAPI initializes Azure Monitor OpenTelemetry only when `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=true` and `APPLICATIONINSIGHTS_CONNECTION_STRING` is present. If packages, exporter setup, or the telemetry endpoint fail, the API continues serving requests and structured logs remain the primary local evidence.

Application Insights complements the TASK-066B3 structured event vocabulary. It does not replace the existing safe log and counter model.

## Captured Signals

API request telemetry uses route templates, method, status, duration, request ID, environment, service name, and release version. Public widget operational events reuse names such as `widget.config.served`, `widget.session.created`, `widget.message.accepted`, `widget.message.fallback`, `rate_limit.denied`, and `origin.validation.denied`.

Manual spans are bounded to useful operations such as public config resolution and public message processing. Future publish and rollback spans should use stable operation names and low-cardinality attributes only.

## Privacy Boundary

Telemetry data class is operational metadata only. It must not contain conversation bodies, assistant answers, citation excerpts, draft configuration values, session tokens, preview grants, Authorization headers, cookies, provider prompts, provider responses, signing keys, database URLs, or document contents.

Public widget keys are public identifiers but are not metric dimensions. When needed in structured logs they are pseudonymized. Tenant/customer names are not telemetry dimensions.

## Browser Telemetry Decision

Public widget browser telemetry is disabled for pilot. Admin browser telemetry is also disabled. The initial pilot relies on server-side API/web telemetry, Container Apps logs, Front Door diagnostics, and synthetic browser checks. No Application Insights JavaScript SDK, session replay, DOM recording, input capture, or behavioral analytics is added.

## Source Maps

Public source maps are disabled for `apps/widget` and `packages/widget-sdk`. Private source-map upload is deferred until Azure/Application Insights tooling is reviewed in a live environment. If private upload is not configured, operators should debug frontend issues using release SHA, minified stack category, request ID, and synthetic reproduction.

## Sampling and Retention

Pilot defaults keep near-full sampling for low traffic so errors and failed requests are retained. Sampling is configured by `AZURE_MONITOR_SAMPLING_RATIO` and must not drop critical errors. Log Analytics retention remains modest: staging 14 days and pilot 30 days unless an approved operational need changes it.

## Infrastructure Diagnostics

The B3 diagnostic module defines Log Analytics routing for Container Apps console/system logs, Container App metrics, Front Door access/health/WAF logs, PostgreSQL operational logs and metrics, Key Vault audit events, and Storage transaction metrics. Verbose SQL statement logging is not enabled.

## Alerts and Action Groups

Action groups are parameterized with `actionGroupEmailReceivers` and `actionGroupWebhookReceivers`. No personal receiver address is committed. Provider-neutral severities map to Azure as: critical -> Sev1, incident -> Sev2, warning -> Sev3.

`deployment/widget/alerts.json` remains the provider-neutral source. B3 maps feasible alert IDs into Azure Monitor scheduled queries or availability tests and keeps runbook references on alert tags.

## Uptime and Synthetic Monitoring

Application Insights web tests cover API `/health/live`, web availability, widget iframe HTML, and SDK v1 alias. These are lightweight and do not call the full AI message endpoint every minute. Deep synthetic message/RAG checks remain deployment-time and lower-frequency work for TASK-068B4.

## Dashboards and KQL

Workbook template: `infrastructure/azure/monitoring/workbooks/controlled-pilot-observability.workbook.json`.

Query pack: `infrastructure/azure/monitoring/queries/`.

Primary support flow is request-ID lookup with `request-id-correlation.kql`. Queries avoid selecting body, answer, citation, token, draft, or secret fields.

## Validation

Run:

```bash
npm run azure:observability:validate
npm run infra:azure:validate
```

These are static checks and do not require Azure credentials. Live monitoring health is not verified until B4 staging deployment and monitoring validation.

## TASK-068B4 Live Validation Hooks

Live staging validation now has repository commands for telemetry, alert, and browser-smoke evidence. These commands remain staging-only and write redacted artifacts under `artifacts/azure-staging-validation/`.

B4 does not change the B3 browser telemetry decision: public widget and admin browser clients still do not send direct Application Insights telemetry. Live monitoring must be proven by Application Insights/Log Analytics evidence from the deployed staging stack before it is marked verified-live.
