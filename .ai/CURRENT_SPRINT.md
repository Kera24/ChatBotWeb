# Current Sprint

Current phase:
Sprint 3H - Controlled Production Pilot Deployment

Current task:
TASK-068B5 - Production-Pilot Domain Wiring, Deployment, Synthetic Validation, Manual Accessibility/Security Gate, and First Pilot Enablement

## Guardrails

- Implement TASK-068B5 repository hardening and promotion gating only.
- Do not deploy production-pilot, modify production DNS, enable real customers, use customer data, weaken auth, or log tokens/conversations/drafts/citations.
- Do not start product eval work until the application is hardened, deployed, monitored, and usable.
- Preserve the existing uncommitted chatbot dashboard implementation.
- Preserve Azure architecture, immutable artifacts, exact-origin policy, tenant isolation, privacy-preserving telemetry, protected approvals, and rollback model.

## Current implementation note

- TASK-068B5 adds an explicit production-pilot readiness validator and protected workflow gate before Azure login or pilot mutation.
- The gate requires successful TASK-068B4 staging validation evidence, live browser/tenant-isolation evidence, telemetry and alert evidence, rollback drill evidence, and manual accessibility/security/domain/rollback/support/first-pilot approvals.
- Live production-pilot execution remains manual through the protected `production-pilot` GitHub environment and has not been performed by this repository change.
