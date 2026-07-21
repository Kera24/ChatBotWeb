# TASK-067B5 - Widget Administration Security Hardening, Authenticated Browser E2E, Accessibility, and Pilot Admin Release Gate

Status: Implemented
Sprint: Sprint 3G - Widget Administration and Publishing
Date: 2026-07-21

## Objective

Harden the widget administration lifecycle implemented in TASK-067B1 through TASK-067B4 and add an evidence-based controlled-pilot administration release gate.

## Scope

- Authenticated admin workflow regression evidence.
- Tenant-isolation and RBAC regression tests.
- Preview-grant security assertions.
- Publish and rollback concurrency hardening tests.
- Knowledge-scope isolation and readiness edge-case tests.
- Public key, origin, embed, and installation-evidence hardening tests.
- Audit completeness checks.
- Admin frontend tests for preview, publish, history, rollback, embed, conflict, and token non-disclosure behavior.
- Machine-readable admin readiness report.
- CI integration for the admin release gate.

## Out of Scope

- Production deployment.
- GA declaration.
- Product analytics or telemetry.
- Lead capture, human handoff, streaming, or new widget runtime features.
- Broad operational-control UI.
- Monitoring vendor integration.

## Implementation Summary

- Added `apps/api/tests/test_widget_admin_b5_hardening.py` for route-denial, stale publish/rollback, preview-grant, knowledge-scope, key-rotation, installation-evidence, and audit hardening.
- Extended `apps/web/components/widgets/widget-admin.test.tsx` to cover B4/B5 admin surfaces: Knowledge, Preview, Publish, History/Rollback, Embed, conflict handling, preview iframe sandbox/title, and token non-rendering.
- Added `scripts/widget-admin-readiness.mjs` to generate `artifacts/widget-admin-readiness/report.json`.
- Added root scripts:
  - `npm run widget:admin:e2e`
  - `npm run widget:admin:a11y`
  - `npm run widget:admin:security`
  - `npm run widget:admin:release:verify`
- Updated CI to run the admin release gate and upload the admin readiness report.

## Evidence Model

The B5 gate is local/CI evidence, not production proof. It combines API hardening tests, admin frontend workflow tests, existing public widget pilot verification, existing pilot readiness, production inspection through the pilot gate, and a generated readiness report.

## Full Preview Decision

Configuration-faithful preview remains intentionally retained. Full conversational/RAG draft preview is deferred because it requires a separate preview session/message boundary beyond the current secure public anonymous session model. This is not a controlled-pilot blocker for configuration publishing.

## Acceptance Classification

Administration is classified as ready for controlled pilot use when `npm run widget:admin:release:verify`, `npm run widget:pilot:verify`, and `npm run widget:pilot:readiness` pass. It is not GA-ready until production deployment, monitoring integration, real production smoke, manual assistive-technology review, and pilot feedback are complete.

## Next Recommended Task

TASK-068A - Controlled Pilot Deployment, Production Domain Wiring, Monitoring Integration, and Post-Deploy Validation Architecture
