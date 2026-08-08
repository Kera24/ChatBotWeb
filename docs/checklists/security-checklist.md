# Security Checklist

## Required validation

- Full `api:test` suite including tenant-isolation and RBAC tests.
- `git diff --check`; manual review of any new logging statement for secret-shaped content.

## Things to verify

- Every tenant-scoped query filters by `organisation_id` **and** `workspace_id`.
- Every tenant-scoped route re-validates fetched-row tenant IDs (404 on mismatch, never 403 — don't leak existence).
- No new RBAC bypass — `require_organisation_role`/`require_super_admin` extended, never routed around.
- No secret, password, session token, API key, or full prompt/response content logged/persisted outside `app.operations.logging.redact`/`app.observability.redaction`.
- `.env*`, `apps/api/app/core/config.py` secret-shaped fields, Stripe/Azure credentials are never printed, committed, or sent anywhere.
- CORS/origin validation (`docs/adr/0008-origin-validation-policy.md`) unaffected by the change unless that's explicitly the point of it.

## Common mistakes

- Adding a debug log line with a raw request/response body "temporarily."
- Filtering by only one of `organisation_id`/`workspace_id`.
- Returning 403 instead of 404 on tenant mismatch.

## Required documentation

- Update `docs/engineering/security.md` if a new security control is added; note any change to rate-limiting/CORS/origin policy against its governing ADR.

## Definition of Done

No tenant-isolation gaps found; no secret-shaped data in logs/traces outside redaction; RBAC verified via test, not just inspection.
