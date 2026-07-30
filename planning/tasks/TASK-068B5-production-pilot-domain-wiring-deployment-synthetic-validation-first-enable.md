# TASK-068B5 - Production-Pilot Domain Wiring, Deployment, Synthetic Validation, Manual Gate, and First Pilot Enablement

Status: Implemented repository hardening gate; live production-pilot execution remains manual and requires protected GitHub environment approval.

## Scope

TASK-068B5 is the final controlled-pilot hardening task after the Azure staging deployment and validation chain. It prevents production-pilot mutation until the repository can prove all required B4 staging evidence and manual security/accessibility signoffs exist.

This task covers:

- production-pilot promotion readiness validation
- required live staging evidence gating
- manual accessibility and security review evidence
- production-pilot domain/TLS/header review acknowledgement
- rollback operator readiness acknowledgement
- support/alert receiver readiness acknowledgement
- first pilot tenant approval acknowledgement
- no-customer-data validation evidence acknowledgement
- protected GitHub workflow gating before Azure login
- safe, machine-readable readiness reporting

It does not deploy production-pilot automatically, enable real customer widgets, change production DNS, or begin product eval work.

## Dependencies

- TASK-068B1 Azure infrastructure foundation
- TASK-068B2 release promotion and rollback automation
- TASK-068B3 Azure Monitor, alerts, dashboards, and uptime layer
- TASK-068B4 live Azure staging validation, tenant isolation, telemetry, alert validation, and rollback drill evidence

## Acceptance Criteria

- `npm run azure:pilot:readiness` validates a staged release manifest, widget release integrity, B4 evidence, rollback evidence, telemetry/alert evidence, and manual gate evidence.
- `.github/workflows/azure-promote-pilot.yml` downloads the `azure-staging-validation` artifact and runs the B5 readiness validator before Azure login, what-if, migration, app deployment, or static publication.
- Manual workflow inputs default to `false` and require explicit operator confirmation for accessibility, security, domain, rollback, support, and first-pilot approval gates.
- Readiness reports are written under `artifacts/production-pilot-readiness/` without secrets, approval-note body text, customer data, tokens, message text, answers, or citations.
- Missing or failed B4 staging evidence blocks production-pilot promotion.
- Missing manual accessibility/security review blocks production-pilot promotion.
- Production-pilot remains protected by the `production-pilot` GitHub environment.

## Current Status

Repository implementation is complete. Live production-pilot execution is not performed by this task and remains blocked until an operator supplies successful B4 staging artifacts and explicit production-pilot approval inputs in the protected workflow.

## Relationship To Dashboard Work

The uncommitted chatbot dashboard implementation does not conflict with this task. B5 gates deployment promotion and first pilot enablement; it does not require additional dashboard placeholder pages to be implemented and does not depend on eval work.

## Validation

Run:

```bash
npm run azure:release:test
npm run azure:pilot:readiness -- --manifest <staging-manifest> --release-dir <widget-release> --staging-report <b4-report> --browser-smoke <b4-browser> --telemetry <b4-telemetry> --alerts <b4-alerts> --rollback <b4-rollback> --manual-gate <manual-gate>
npm run verify
git diff --check
```

## Next Step

After this gate passes with live B4 evidence and protected approval, operators may run the manual production-pilot promotion workflow. Product evals should begin only after the pilot environment is deployed, monitored, smoke-tested, and usable.
