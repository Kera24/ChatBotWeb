# Azure Application Deployment Runbook

## Purpose

This runbook describes the controlled staging and production-pilot release process introduced by TASK-068B2.

Do not use this process to enable customer widgets automatically. Tenant/widget pilot enablement remains operational/manual.

## 1. Verify Repository Gates

Run or confirm the exact SHA has passed:

```bash
npm run verify
npm run widget:admin:release:verify
npm run widget:pilot:verify
npm run widget:pilot:readiness
npm run infra:azure:validate
npm run azure:release:test
```

## 2. Validate Infrastructure

Run local validation:

```bash
npm run infra:azure:validate
```

Run Azure what-if from the workflow or an approved Azure login:

```bash
npm run infra:azure:whatif -- staging
```

Review potentially destructive changes manually.

## 3. Confirm Secrets

Confirm required Key Vault secrets exist by name. Do not print values.

Required secret names are listed in `docs/06_Operations/Azure_Secret_Bootstrap_Runbook.md`.

## 4. Build Release

Staging workflow builds and pushes:

- API image tagged with Git SHA
- web image tagged with Git SHA

It records digest refs in `artifacts/deployment-release/manifest.json`.

## 5. Deploy Staging

Use the manual `Azure Deploy Staging` workflow.

Inputs:

- `git_ref`
- `deploy_infrastructure`
- `deploy_application`

Staging runs gates, what-if, optional infrastructure deployment, image build/push, migration job, Container Apps revision deployment, static widget publish, and deployed smoke.

## 6. Run Migrations

The workflow runs:

```bash
npm run azure:migrate -- --environment staging --image <api-image-digest> --execute
```

If migration fails, stop deployment and keep the previous running release.

## 7. Verify Health

Verify:

- API live
- API ready
- web availability
- SDK availability
- widget iframe availability

B4 must add full live browser smoke before real pilot customer enablement.

## 8. Review Deployment Report

Review:

- `artifacts/deployment-release/manifest.json`
- `artifacts/azure-deployment/staging/report.json`
- `artifacts/azure-deployment/staging/smoke-report.json`

No secrets should appear.

## 9. Approve Pilot Promotion

Only after staging evidence is accepted, trigger `Azure Promote Pilot` with the staging workflow run ID.

Production-pilot requires GitHub environment approval.

## 10. Promote Known-Good Artifacts

Pilot promotion downloads the staging artifact and uses the recorded image refs and widget release artifacts. It does not rebuild.

## 11. Run Pilot Smoke

Pilot smoke verifies health and static endpoints. B4 must add the full live FastAPI browser smoke.

## 12. Customer Enablement Boundary

After B2, deployment automation may be ready, but customer enablement remains blocked until later gates:

- monitoring/alerts in B3
- staging live smoke and rollback drill in B4
- production pilot deployment and manual accessibility/security checks in B5
