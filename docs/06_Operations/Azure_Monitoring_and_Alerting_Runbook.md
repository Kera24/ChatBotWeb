# Azure Monitoring and Alerting Runbook

Status: TASK-068B3 configured, live validation pending TASK-068B4

## Dashboard

Open the controlled-pilot Azure Workbook after deployment. Review API health, web health, widget/CDN availability, public widget config/session/message signals, dependency failures, release comparison, and synthetic availability.

## Request ID Lookup

Use `infrastructure/azure/monitoring/queries/request-id-correlation.kql` with the customer-provided `X-Request-ID`. Do not ask for session tokens, browser storage dumps, Authorization headers, preview grants, or conversation text.

## Alert Response

Classify by alert ID and severity. Confirm the alert tags include the provider-neutral `alert_id` and runbook path. Preserve request IDs, timestamps, status categories, release version, and safe error categories.

## API Outage

Check availability results, Container Apps revision health, API `/health/live`, API `/health/ready`, recent 5xx by route, and the active release SHA. If a new release correlates with failures, use the Azure rollback planner and run post-rollback smoke.

## Database Pressure

Check PostgreSQL CPU, connections, storage, failed connections, and readiness DB failure events. Do not enable verbose SQL or query-parameter logging during incident response without a privacy review.

## Message or Provider Issue

Use public message failure and fallback queries. Fallback is informational unless sustained above expected levels or accompanied by provider/retrieval errors. Do not inspect prompts, completions, retrieved chunks, or citation text through telemetry.

## Front Door Issue

Check Front Door health probes, access status trends, origin health, WAF events, and certificate status. Confirm no preview token or grant is transported through query strings.

## Synthetic Smoke Failure

Lightweight uptime failures are investigated through Application Insights availability tests. Deep browser/message synthetic failures become deployment blockers in B4 and may later become scheduled operational alerts. Tenant-isolation synthetic failure is critical; contain by disabling the affected widget/tenant or public widgets globally.

## Release Comparison

Use `deployment-release-comparison.kql` to compare failure rate and p95 latency before and after a release version. Use this evidence in rollback decisions.

## Safe Test Alert Procedure

In staging, use a temporary test action-group receiver or a controlled synthetic endpoint failure. Do not cause a production outage. Production-pilot alert receiver tests require release-owner approval.
