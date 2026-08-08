# Prompt Template: Backend API

Use this when the task is adding/changing a FastAPI route, repository function, or service in `apps/api`.

## Scope

`apps/api/app/api/v1/*`, `apps/api/app/repositories/*`, `apps/api/app/services/*`, `apps/api/app/schemas/*`. See `docs/architecture/backend.md` and `docs/architecture/authentication.md`.

## Constraints

- RBAC via `require_organisation_role({...})`, matching the nearest precedent for the data's sensitivity (viewer-inclusive vs. owner/admin-only — see `docs/architecture/backend.md`).
- Repository functions are plain functions (`db: Session` first arg), not classes.
- Every tenant-scoped query filters by `organisation_id` **and** `workspace_id`; every detail-fetch re-verifies the fetched row's tenant IDs match (404 on mismatch, never 403 — don't leak existence).
- Response shape: `app.schemas.common.success_response(data, meta)`.
- New router → register in `app/api/v1/router.py`'s `API_V1_ROUTER_REGISTRATIONS`.
- Do not modify database schema/write a migration unless explicitly asked.

## Validation

`npm run api:test` at minimum (see `docs/validation-policy.md`). If the change touches `app/ai/*` or `app/evaluation/*`, also run `npm run eval:test`.

## Reporting

Short Report by default (`docs/reporting-policy.md`).

## Expected output

New/modified route + repository + schema files, a new/extended test file in `apps/api/tests/` following the nearest existing fixture convention (no shared `conftest.py` — copy the nearest similar file's `client` fixture).

## What NOT to modify

- Existing endpoint signatures/response shapes relied on by the frontend or other callers — add new optional fields instead of changing existing ones.
- `app/core/config.py` beyond adding new settings following the existing `getenv`/`_get_int`/`_get_float` pattern.
- Anything in `app/billing/`, `app/evaluation/policy.py`, `app/evaluation/gate.py` unless the task is specifically about billing or evaluation thresholds.
