# Azure Staging Validation and Rollback Drill Runbook

Status: TASK-068B4 repository harness implemented; live staging execution requires Azure staging credentials and secure parameters.

## Purpose

This runbook validates the complete controlled-pilot stack in the Azure `staging` environment only. It exercises infrastructure, deployment, migration, widget publication, live smoke, tenant isolation, observability, alert routing, and rollback evidence without enabling real customers or production-pilot.

## Safety Rules

- Target only `staging` for TASK-068B4 direct execution.
- Do not use customer data, customer tenants, or customer widgets.
- Do not deploy `pilot`, `production`, `prod`, or `production-pilot` from this workflow.
- Do not print secret values, connection strings, tokens, preview grants, messages, answers, citations, prompts, or draft configuration.
- Stop immediately for tenant leakage, token leakage, preview-grant leakage, unauthorized origin acceptance, secret leakage, migration corruption, or failed rollback without recovery.

## Prerequisites

Verify before mutation:

```bash
npm run azure:staging:validate -- --environment staging
```

Required live inputs include Azure CLI, Bicep, selected subscription, OIDC or safe interactive login, approved staging resource group, Key Vault secret names, PostgreSQL administrator secret, provider secrets, Application Insights configuration, and staging endpoint variables.

The command writes:

- `artifacts/azure-staging-validation/infrastructure.json`
- `artifacts/azure-staging-validation/report.json`

A `blocked_missing_prerequisites` result is expected when credentials or secure staging parameters are absent. Do not treat that as live staging evidence.

## Repository Gates

Run before Azure mutation:

```bash
npm run verify
npm run widget:admin:release:verify
npm run widget:pilot:verify
npm run widget:pilot:readiness
npm run infra:azure:validate
npm run azure:observability:validate
npm run azure:release:test
npm run widget:inspect:production
npm run widget:bundle:check
```

Deployment stops if any gate fails.

## Azure What-If

Run what-if through the protected workflow or an approved Azure login:

```bash
npm run infra:azure:whatif -- staging
npm run azure:staging:validate -- --environment staging --execute
```

Review proposed deletes or replacements for PostgreSQL, Storage Account, Key Vault, Container Apps environment, and Front Door profile before deployment.

## Deployment Sequence

1. Deploy or update staging infrastructure from `infrastructure/azure/main.bicep` and `staging.bicepparam`.
2. Verify required Key Vault secret names exist without printing values.
3. Verify managed identity and RBAC for API, web, ACR pull, Blob access, Key Vault secret reads, and deployment actions.
4. Build API and web images from the approved Git SHA; tag by SHA and record digests.
5. Generate the deployment release manifest.
6. Run the migration Container Apps job with `alembic upgrade head`.
7. Bootstrap only synthetic Alpha/Beta tenants, widgets, origins, and knowledge corpus.
8. Deploy API and web Container App revisions and validate live readiness before traffic shift.
9. Publish widget/SDK static artifacts through the safe B2 publication sequence.
10. Validate Front Door endpoints, cache headers, security headers, CORS, source-map policy, and direct-origin exposure.

## Live Smoke

Run:

```bash
npm run azure:staging:browser -- --environment staging --execute
```

The live browser suite must use the staging SDK, iframe, API, PostgreSQL/pgvector, storage, and configured staging provider strategy. It must verify positive same-tenant retrieval, negative cross-tenant retrieval, cross-widget session rejection, origin isolation, token isolation, no cookies, and no sensitive postMessage or console output.

## Telemetry and Alerts

Run:

```bash
npm run azure:staging:telemetry -- --environment staging --execute
npm run azure:staging:alerts -- --environment staging --execute
```

Validate Application Insights request telemetry, request ID correlation, release/environment tags, dependency telemetry, structured operational events, privacy canary absence, workbook availability, KQL queries, action-group routing, and alert rule scopes.

## Rollback Drill

Use two harmless staging releases: current and known-good target. Do not create a breaking migration for the drill.

```bash
npm run azure:staging:rollback-drill -- --environment staging --current <current-manifest> --to <known-good-manifest> --execute
```

The planner must check Alembic head, API version, protocol major, and artifact checksums. Rollback does not downgrade databases. After rollback, verify API live/ready, web, SDK, widget, config/session/message smoke, tenant isolation, and telemetry release tags. Then roll forward to the intended latest staging release and smoke again.

## Evidence Review

Review these safe machine-readable artifacts:

- `artifacts/azure-staging-validation/infrastructure.json`
- `artifacts/azure-staging-validation/report.json`
- `artifacts/azure-staging-validation/browser-smoke.json`
- `artifacts/azure-staging-validation/telemetry.json`
- `artifacts/azure-staging-validation/alerts.json`
- `artifacts/azure-staging-validation/rollback.json`

Do not upload authenticated browser storage state. Evidence may contain synthetic tenant labels but must not contain secrets, customer data, messages, answers, citations, prompts, or draft values.

## Classification

Use one classification:

- `staging validated and ready for production-pilot preparation`
- `staging deployed with named blockers`
- `staging deployment blocked before execution`
- `staging validation failed`

Do not recommend production-pilot execution until staging passes without unresolved critical blockers.
