# Current Sprint

Current phase:
Sprint 3G - Widget Administration and Publishing

Current task:
TASK-067B4 - Widget Preview, Publish Workflow, Revision History, Rollback, Knowledge Scope, and Embed Verification

## Guardrails

- Implement authenticated widget administration workflow completion only: knowledge scope, draft preview, publish validation/confirmation, publish execution, revision history, rollback, and passive embed installation evidence.
- Do not implement production deployment, GA, analytics dashboards, product telemetry, arbitrary external crawling, SSRF-prone URL verification, global operational-control UI, streaming, lead capture, or human handoff.
- Preserve revision immutability, tenant isolation, public/draft separation, pilot/operational separation, exact origins, token isolation, and secure iframe boundaries.
- Next recommended task: TASK-067B5 - Widget Administration Security Hardening, Authenticated Browser E2E, Accessibility, Audit, and Pilot Admin Release Gate.
