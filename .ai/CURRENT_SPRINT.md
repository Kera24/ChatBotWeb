# Current Sprint

Current phase:
Sprint 3G - Widget Administration and Publishing

Current task:
TASK-067A - Widget Administration, Publishing, and Embed Management Architecture

## Guardrails

- TASK-067A is architecture and planning only.
- Do not implement admin UI, publishing APIs, migrations, runtime behavior, deployment infrastructure, or production deployment in TASK-067A.
- Publication, pilot enablement, operational status, public key state, and release channel must remain distinct concepts.
- Admin implementation must preserve tenant isolation, immutable published revisions, auditability, and public widget runtime boundaries.
- The widget remains controlled-pilot ready, not GA.