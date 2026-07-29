# TASK-068B4 - Azure Staging Deployment, Live Full-Stack Validation, Monitoring Verification, and Rollback Drill

Status: Implemented repository harness; live staging execution blocked until Azure staging credentials and secure parameters are available.
Sprint: Sprint 3H - Controlled Production Pilot Deployment
Type: Azure staging validation, live evidence, and rollback drill orchestration

## Objective

Deploy and validate the complete platform in an actual Azure staging environment, exercising infrastructure, deployment, monitoring, security, and rollback systems created in TASK-068B1 through TASK-068B3.

## Scope Implemented

- Added staging-only validation commands for prerequisite, browser smoke, telemetry, alert, and rollback evidence.
- Added the staging-only synthetic-widget bootstrap Container Apps Job module and workflow/script wiring so Alpha/Beta synthetic fixtures are seeded through the deployed API image and managed identity runtime configuration.
- Added a manual GitHub Actions workflow for protected staging live validation.
- Added redacted evidence generation under `artifacts/azure-staging-validation/`.
- Added regression tests that reject non-staging B4 execution and verify workflow guardrails.
- Added staging validation and rollback drill runbook.
- Added staging live-validation evidence engineering documentation.
- Updated release, admin, and security checklists to distinguish repository configured, staging verified, and production-pilot verified states.

## Non-Scope and Safety

- No production-pilot deployment is performed by this task.
- No customer data, real customer widget, or production database is used.
- No live staging deployment is claimed unless Azure execution actually occurs.
- Scripts reject direct B4 execution against `pilot`, `production`, `prod`, and `production-pilot`.
- Evidence redacts token-like, secret-like, connection-string, preview-grant, session, authorization, cookie, and key fields.

## Commands Added

```bash
npm run azure:staging:validate
npm run azure:staging:browser
npm run azure:staging:telemetry
npm run azure:staging:alerts
npm run azure:staging:rollback-drill
npm run azure:staging:seed-synthetic-widgets
npm run azure:staging:seed-synthetic-widgets:job
```

## Expected Live Evidence

A credentialed staging run must generate:

- `artifacts/azure-staging-validation/infrastructure.json`
- `artifacts/azure-staging-validation/report.json`
- `artifacts/azure-staging-validation/browser-smoke.json`
- `artifacts/azure-staging-validation/telemetry.json`
- `artifacts/azure-staging-validation/alerts.json`
- `artifacts/azure-staging-validation/rollback.json`

These artifacts must contain synthetic operational metadata only and no secrets, customer data, messages, answers, citations, prompts, or draft values.

## Current Execution Classification

Repository configuration is implemented. If local or CI Azure prerequisites are absent, the correct classification is:

`staging deployment blocked before execution`

Do not recommend TASK-068B5 as executable until staging passes without unresolved critical blockers.

## Validation Commands

- `npm run azure:release:test`
- `npm run azure:staging:validate`
- `npm run infra:azure:validate`
- `npm run azure:observability:validate`
- `npm run verify`
- `git diff --check`

## Next Recommended Task

After successful live staging validation with no unresolved critical blockers:

TASK-068B5 - Production-Pilot Domain Wiring, Deployment, Synthetic Validation, Manual Accessibility/Security Gate, and First Pilot Enablement
