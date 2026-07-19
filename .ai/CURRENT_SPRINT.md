# Current Sprint

Current phase:
Sprint 3F - Widget Pilot and Operations

Current task:
TASK-066B1 - Widget Production Delivery, Security Headers, Caching, and Versioning

## Guardrails

- TASK-066B1 implements repository-local release artifacts, validation, cache/header policy, CI verification, and documentation only.
- Do not deploy production infrastructure, change DNS, provision cloud/CDN resources, add monitoring vendors, or implement admin publishing UI in TASK-066B1.
- Generated release artifacts under `artifacts/widget-release/` are build outputs and must not be committed.
- Session tokens, messages, answers, citations, drafts, and idempotency keys must remain isolated inside the iframe/public API boundary.
- The next recommended task is TASK-066B2 - Real-Backend Synthetic Smoke, Tenant Isolation, and Pilot Release Verification.
