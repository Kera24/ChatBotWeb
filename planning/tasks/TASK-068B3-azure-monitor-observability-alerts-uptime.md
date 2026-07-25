# TASK-068B3 - Azure Monitor, Privacy-Preserving Telemetry, Alerts, Uptime, and Operational Dashboards

Status: Implemented
Sprint: Sprint 3H - Controlled Production Pilot Deployment
Type: Azure observability implementation, static validation, and runbook documentation

## Objective

Implement the Azure observability layer required for controlled-pilot operation without deploying production automatically or adding product analytics.

## Scope Implemented

- Azure Monitor and workspace-based Application Insights configuration in Bicep.
- Optional FastAPI Azure Monitor OpenTelemetry startup integration.
- Safe request correlation and normalized route telemetry.
- Public widget operational event forwarding into the active OpenTelemetry span when configured.
- Expanded redaction for preview grants, draft configuration, provider prompts, connection strings, and signing keys.
- Container Apps runtime configuration for App Insights connection string as a server-side secret/env value.
- Azure Monitor action group and availability-test architecture.
- Azure scheduled-query alerts mapped to provider-neutral alert IDs where feasible.
- Azure diagnostic-settings module for Container Apps, Front Door, PostgreSQL, Key Vault, and Storage.
- KQL query pack and controlled-pilot workbook template.
- Public widget and SDK public source maps disabled for pilot delivery.
- `npm run azure:observability:validate` static validation and CI integration.
- Observability engineering doc and Azure monitoring/alerting runbook.

## Non-Scope

- No Azure apply/deployment was run.
- No production, staging, DNS, or customer configuration was mutated.
- No product analytics, session replay, DOM recording, draft capture, message capture, answer capture, or citation-content capture was added.
- Public widget and admin browser apps do not send telemetry directly to Application Insights.

## Validation Commands

- `npm run azure:observability:validate`
- `python -m compileall apps/api/app`
- `npm run api:test`
- `npm run web:test`
- `npm run widget:test`
- `npm run widget-sdk:test`
- `npm run infra:azure:validate`
- `npm run verify`
- `git diff --check`

Azure what-if should include the monitoring resources once Azure credentials and secure parameters are available. Do not apply from this task.

## Next Recommended Task

TASK-068B4 - Azure Staging Deployment, Live Full-Stack Browser Smoke, Synthetic Tenant Isolation, Monitoring Validation, and Rollback Drill
