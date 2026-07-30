# Azure Production-Pilot Enablement Runbook

Status: protected manual workflow only.

## Prerequisites

- Azure staging validation succeeded with B4 evidence artifacts.
- `azure-staging-deployment` and `azure-staging-validation` artifacts exist for the same reviewed staging run.
- Manual accessibility review passed for the pilot scope.
- Manual security review passed with no unresolved critical blockers.
- Production-pilot domain, TLS, DNS, CSP, CORS, cache, and header plan reviewed.
- Rollback operator has a known-good manifest and rollback runbook ready.
- Support contact and alert receiver path are ready.
- First pilot tenant/widget enablement is approved.
- Validation evidence contains no customer data.

## Promotion

1. Open the `Azure Promote Pilot` workflow.
2. Provide the staging workflow run ID.
3. Enter a human-readable approval note.
4. Set every manual gate input to `true` only after the corresponding review is complete.
5. Submit the workflow and wait for the `Validate production-pilot readiness gate` step.
6. Stop if readiness fails. Do not bypass by editing artifacts.
7. If readiness passes, the workflow proceeds to Azure login, pilot what-if, migration, Container Apps revision deployment, widget static publication, and deployed smoke.

## Blocker Response

Stop promotion when any of these fail:

- live tenant-isolation or browser smoke
- telemetry privacy canary
- alert routing
- rollback drill
- manual accessibility review
- manual security review
- production domain/header review
- rollback operator readiness
- support readiness

Do not enable a real customer widget until the production-pilot deployed smoke and monitoring checks are complete.

## Evidence

Keep these artifacts:

- `artifacts/deployment-release/manifest.json`
- `artifacts/widget-release/manifest.json`
- `artifacts/azure-staging-validation/*.json`
- `artifacts/production-pilot-readiness/report.json`
- `artifacts/azure-deployment/pilot/smoke-report.json`

Never copy secrets, message text, answers, citations, preview grants, session tokens, or database credentials into evidence.
