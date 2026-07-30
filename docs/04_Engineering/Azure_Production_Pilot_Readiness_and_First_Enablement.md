# Azure Production-Pilot Readiness and First Enablement

Status: TASK-068B5 repository gate implemented. Live production-pilot deployment is manual and protected.

## Purpose

Production-pilot is a controlled operational environment, not GA. Promotion is allowed only after a staged release has passed repository gates, live Azure staging validation, telemetry and alert checks, rollback drill evidence, and explicit manual security/accessibility review.

## Gate Command

```bash
npm run azure:pilot:readiness -- \
  --manifest artifacts/deployment-release/manifest.json \
  --release-dir artifacts/widget-release \
  --staging-report artifacts/azure-staging-validation/report.json \
  --browser-smoke artifacts/azure-staging-validation/browser-smoke.json \
  --telemetry artifacts/azure-staging-validation/telemetry.json \
  --alerts artifacts/azure-staging-validation/alerts.json \
  --rollback artifacts/azure-staging-validation/rollback.json \
  --manual-gate artifacts/production-pilot-readiness/manual-gate.json
```

The command writes `artifacts/production-pilot-readiness/report.json`.

## Required Evidence

- Deployment manifest from staging with passed admin, pilot verification, and pilot readiness gates.
- Widget release artifacts matching the manifest checksums.
- B4 staging report classified as passed or validated with no critical blockers.
- Live browser smoke and tenant-isolation evidence.
- Telemetry privacy/correlation evidence.
- Alert routing evidence.
- Rollback drill evidence.
- Manual gate evidence confirming accessibility, security, domain, rollback, support, first-pilot approval, and no-customer-data conditions.

## Privacy Boundary

The readiness report records paths, statuses, release identifiers, and gate outcomes only. It must not include approval note body text, customer data, message text, answers, citations, preview grants, session tokens, database credentials, connection strings, or secrets.

## Workflow Enforcement

`.github/workflows/azure-promote-pilot.yml` downloads both `azure-staging-deployment` and `azure-staging-validation` artifacts from the selected staging run. It records explicit manual gate inputs and runs `npm run azure:pilot:readiness` before Azure login. If the gate fails, no pilot what-if, migration, app deployment, or static publication runs.

## Live Execution Status

This repository change does not deploy production-pilot or modify DNS. Operators must still run the protected workflow and review live results before enabling any real customer widget.
