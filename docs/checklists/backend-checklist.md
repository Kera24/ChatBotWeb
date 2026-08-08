# Backend Checklist

## Required validation

- `npm run api:test` (`docs/validation-policy.md`); `npm run eval:test` in addition if `apps/api/app/evaluation/**` was touched.
- `git diff --check` before finishing.

## Things to verify

- New endpoints live in `app/api/v1/<feature>.py`, registered in `API_V1_ROUTER_REGISTRATIONS` (`app/api/v1/router.py`).
- RBAC via `require_organisation_role({...})`, matching the nearest precedent (`conversations.py` viewer-inclusive, `audit_events.py` owner/admin-only) — never a new bypass mechanism.
- Repository functions in `app/repositories/<feature>_repository.py` are plain functions taking `db: Session` first, not classes.
- Every tenant-scoped query filters by `organisation_id` **and** `workspace_id`; every tenant-scoped route re-validates the fetched row's tenant IDs (404, not 403, on mismatch).
- Type hints everywhere; `Session` passed explicitly, no ambient DB context.
- New optional trailing fields preferred over changing an existing function/endpoint signature.

## Common mistakes

- Filtering by `organisation_id` only and forgetting `workspace_id` (or vice versa).
- Returning 403 instead of 404 on a tenant mismatch (leaks existence).
- Writing a repository as a class instead of plain functions.
- Routing around `require_organisation_role` with a custom check "just for this endpoint."
- Restructuring an existing signature instead of adding a trailing optional field.

## Required documentation

- Update `docs/architecture/backend.md` or the relevant `docs/architecture/*.md`/`docs/engineering/*.md` page if behavior changes.
- New migration follows `docs/adr/`'s numbered-filename convention if schema changed (only when explicitly asked — `CLAUDE.md`).

## Definition of Done

`api:test` (and `eval:test` if applicable) pass with the same or higher test count than before; every new/changed route has an RBAC dependency and correct tenant-scope filtering verified by a test; `git diff --check` is clean.
