# Task: Database and Tenancy Foundation

## Task ID

TASK-005

## Linked epic/story

- EPIC-002

## Objective

Add the backend database foundation for tenant management, including SQLAlchemy models, Alembic migrations, database session configuration, tenant-scoped repository patterns, tests, and local database setup documentation.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `docs/02_Architecture/02_Database_Design.md`
- `docs/06_Security/01_Security_and_RBAC_Model.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `planning/epics/EPIC-002-tenant-management.md`

## Files to create or modify

- `apps/api/app/core/config.py`
- `apps/api/app/db/session.py`
- `apps/api/app/db/base.py`
- `apps/api/app/db/models/`
- `apps/api/app/repositories/`
- `apps/api/alembic/`
- `apps/api/alembic.ini`
- `apps/api/tests/test_database_models.py`
- `apps/api/tests/test_tenant_isolation_patterns.py`
- `apps/api/requirements.txt`
- `docs/04_Engineering/Database_Local_Setup.md`

## Technical requirements

1. Add SQLAlchemy database setup.
2. Add Alembic migration foundation.
3. Add initial models:
   - Organisation
   - Workspace
   - User
   - Membership
4. Add tenant-scoped model patterns.
5. Add database session config.
6. Add first migration.
7. Add tests for model creation and tenant isolation patterns.
8. Add local database setup documentation.

## Tenant isolation rules

- Tenant isolation is the main priority.
- Do not create repository methods that fetch tenant-scoped records by ID alone.
- Workspace-scoped records must be fetched with organisation_id and workspace_id context.
- Organisation-scoped records must be fetched with organisation_id context.
- Future tenant-owned tables must include organisation_id or workspace_id as required.

## Constraints

- Do not implement auth.
- Do not implement login.
- Do not implement real user invitation flow.
- Do not implement RAG.
- Do not implement document upload.
- Do not implement widget runtime.
- Do not implement analytics.
- Do not implement billing.

## Acceptance criteria

- [ ] SQLAlchemy base and session config exist.
- [ ] Alembic is configured.
- [ ] Initial migration creates organisation, workspace, user, and membership tables.
- [ ] Models can be created in tests.
- [ ] Repository patterns require tenant context for scoped records.
- [ ] Tests prove workspace lookup does not cross organisation boundaries.
- [ ] Local database setup is documented.

## Required checks

- `python -m pytest`
- `alembic upgrade head` if local database is available

## Definition of done

- [ ] Database foundation implemented
- [ ] Tenant isolation patterns tested
- [ ] Migration foundation added
- [ ] No product feature scope creep
- [ ] Ready for future tenant API/auth tasks
