# Task: Tenant API Foundation

## Task ID

TASK-006

## Linked epic/story

- EPIC-002

## Objective

Add the first tenant-management API endpoints for organisations and workspaces using the existing SQLAlchemy models, database session dependency, and tenant-safe repository patterns.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `docs/02_Architecture/03_API_Specification.md`
- `docs/02_Architecture/02_Database_Design.md`
- `docs/06_Security/01_Security_and_RBAC_Model.md`
- `planning/epics/EPIC-002-tenant-management.md`
- `planning/tasks/TASK-005-database-tenancy-foundation.md`

## Files to create or modify

- `apps/api/app/api/deps.py`
- `apps/api/app/api/v1/admin.py`
- `apps/api/app/api/v1/orgs.py`
- `apps/api/app/api/v1/workspaces.py`
- `apps/api/app/api/v1/router.py`
- `apps/api/app/repositories/organisation_repository.py`
- `apps/api/app/repositories/workspace_repository.py`
- `apps/api/app/schemas/`
- `apps/api/tests/test_tenant_api.py`

## Technical requirements

1. Add organisation API endpoints:
   - `GET /api/v1/admin/organisations`
   - `POST /api/v1/admin/organisations`
2. Add workspace API endpoints:
   - `GET /api/v1/orgs/{organisation_id}/workspaces`
   - `POST /api/v1/orgs/{organisation_id}/workspaces`
   - `GET /api/v1/workspaces/{workspace_id}`
3. Use existing repository patterns.
4. Add Pydantic schemas.
5. Add database dependency injection.
6. Add tests for organisation and workspace APIs.
7. Preserve tenant-safe lookup patterns.

## Temporary auth rule

Authentication is not implemented yet.

TASK-006 may use an explicit development-only dependency so routes can be tested locally. This placeholder must be clearly named and must not pretend to be production authentication.

## Tenant isolation rules

- Do not fetch workspace records by `workspace_id` alone.
- `GET /api/v1/workspaces/{workspace_id}` must require `organisation_id` as a query parameter until real auth/tenant context exists.
- Repository functions must require organisation context for workspace-scoped lookups.

## Constraints

- Do not implement login or authentication.
- Do not implement user invitation.
- Do not implement RAG.
- Do not implement document upload.
- Do not implement widget runtime.
- Do not implement analytics.
- Do not implement billing.

## Acceptance criteria

- [ ] Endpoints exist under `/api/v1`.
- [ ] Pydantic request and response schemas exist.
- [ ] Database dependency can be overridden in tests.
- [ ] Tests create and list organisations.
- [ ] Tests create and list workspaces within an organisation.
- [ ] Tests prove workspace detail lookup requires matching organisation context.
- [ ] Auth placeholder is clearly marked development-only.

## Required checks

- `python -m pytest`
- `python -m alembic upgrade head`

## Definition of done

- [ ] Tenant API foundation implemented
- [ ] Tests pass
- [ ] No auth, RAG, document, widget, analytics, or billing scope creep
- [ ] API design concern is documented if workspace detail needs temporary query context
