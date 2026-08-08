# Skill: Backend API

## Purpose

Implement or modify a FastAPI endpoint, repository function, or service in `apps/api`.

## When to use

Any task that adds/changes a backend route, its RBAC, its data access, or its response schema. Not for AI/RAG pipeline internals specifically (use `rag`/`retrieval`), not for evaluation internals (use `evaluation`), not for billing (use `billing`).

## Architecture assumptions

- FastAPI + SQLAlchemy 2.0, sync throughout (no async ORM usage). See `docs/architecture/backend.md`.
- RBAC via `require_organisation_role({...})` dependency factory; two dependency tiers per router (viewer-inclusive vs. owner/admin-only) as module-scope `Annotated` aliases.
- Tenant isolation: every query filters `organisation_id` + `workspace_id`; every detail-fetch re-verifies and 404s (not 403s) on mismatch.
- Response envelope: `success_response(data, meta)`.
- Repositories are plain functions, not classes.

## Files typically modified

- `apps/api/app/api/v1/<feature>.py` (new or existing router).
- `apps/api/app/repositories/<feature>_repository.py`.
- `apps/api/app/schemas/<feature>.py`.
- `apps/api/app/api/v1/router.py` (only if registering a brand-new router).
- `apps/api/tests/test_<feature>_api.py`.

## Files never modified

- `apps/api/app/api/deps.py`'s core RBAC mechanism (`require_organisation_role`, `require_super_admin`) — extend usage of it, don't change its implementation, unless the task is specifically about RBAC itself.
- `apps/api/alembic/versions/*` (unless the task explicitly requires a schema change).
- `apps/api/app/billing/*`, `apps/api/app/evaluation/policy.py` (see those domains' own skills).

## Validation commands

```
npm run api:test
```
Add `npm run eval:test` if `app/ai/*` or `app/evaluation/*` was touched.

## Expected report format

Short Report by default; Full Report if RBAC, tenant-isolation logic, or a public contract changed.

## Common pitfalls

- Filtering by `workspace_id` alone without `organisation_id` (or vice versa) — both are required on every tenant-scoped query.
- Returning 403 instead of 404 on a cross-tenant lookup — leaks existence to an unauthorized caller.
- Introducing a repository *class* when every other repository in the codebase is plain functions.
- Forgetting to register a new router in `API_V1_ROUTER_REGISTRATIONS`.
- Changing an existing endpoint's response shape instead of adding a new optional field, breaking a frontend caller silently (frontend `lib/api/*` types won't catch this at the Python layer — check callers manually).

## Best practices

- Find the nearest existing router with similar sensitivity/RBAC needs (`conversations.py` for viewer-inclusive tenant data, `audit_events.py` for owner/admin-only) and copy its dependency/pattern shape exactly.
- Write the repository function and its test before wiring the route, so tenant-scoping logic is verified in isolation first.
- Grep for all existing callers of anything you're changing before changing its signature.
