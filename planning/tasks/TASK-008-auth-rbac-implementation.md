# Task: Auth and RBAC Implementation Foundation

## Task ID

TASK-008

## Linked epic/story

- EPIC-002

## Objective

Add an API auth/RBAC foundation using explicit development-only current-user behavior, role helpers, membership checks, and route protection for the existing organisation and workspace dashboard APIs.

This task does not implement production login or integrate a hosted auth provider.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `planning/tasks/TASK-007-auth-rbac-foundation.md`
- `docs/06_Security/01_Security_and_RBAC_Model.md`
- `planning/epics/EPIC-002-tenant-management.md`

## Scope

- Add auth/RBAC foundation for API.
- Add development-only current-user dependency clearly marked as temporary.
- Add role/permission helpers.
- Protect organisation and workspace dashboard routes using membership checks.
- Keep public widget routes separate and unauthenticated for now.
- Add tests for required RBAC behavior.

## Temporary development auth behavior

Until production auth is implemented, API tests and local development may use explicit development headers.

These headers are not production auth:

- `X-Development-User-Email`
- `X-Development-Role`

The implementation must clearly label this behavior as temporary and development-only.

## RBAC requirements

- Admin organisation list/create routes require `super_admin`.
- Organisation workspace list/create routes require one of:
  - `super_admin`
  - `org_owner`
  - `client_admin`
- Organisation workspace access for non-super-admin users must verify an active membership for the requested `organisation_id`.
- Workspace detail must preserve `organisation_id + workspace_id` lookup and must enforce organisation access.

## Tests required

- `super_admin` can access admin organisation list.
- Non-`super_admin` cannot access admin organisation list.
- Organisation member can access own organisation workspaces.
- Non-member cannot access another organisation's workspaces.

## Constraints

- Do not implement OAuth/login.
- Do not implement invitations.
- Do not implement password auth.
- Do not implement RAG.
- Do not implement documents.
- Do not implement widget runtime.
- Do not implement billing.
- Do not implement analytics.

## Acceptance criteria

- [ ] Development-only current-user dependency exists and is clearly marked.
- [ ] Role/permission helpers exist.
- [ ] Admin organisation routes enforce `super_admin`.
- [ ] Organisation workspace routes enforce active membership for non-super-admins.
- [ ] Workspace detail route still requires `organisation_id` and uses tenant-safe lookup.
- [ ] Required RBAC tests pass.
- [ ] Existing tenant isolation tests pass.
