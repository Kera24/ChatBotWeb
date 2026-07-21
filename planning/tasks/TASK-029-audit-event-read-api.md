# Task: Audit Event Read API

## Task ID

TASK-029

## Linked epic/story

- EPIC-003

## Objective

Add metadata-only audit event read APIs with strict tenant scoping and existing RBAC placeholder checks.

This task exposes audit event reads only. It does not implement audit UI, analytics dashboards, upload, extraction, chunking, embeddings, RAG, or widget behavior.

## Scope

Implement only:

- Audit event response schema.
- Tenant-scoped audit repository read helpers.
- Organisation-level audit event list endpoint.
- Workspace-level audit event list endpoint.
- Existing development RBAC placeholder checks.
- Tests for allowed roles, non-member denial, cross-tenant isolation, viewer denial, and pagination/limit.
- Sprint pointer update to TASK-029.

## Endpoints

- `GET /api/v1/orgs/{organisation_id}/audit-events`
- `GET /api/v1/workspaces/{workspace_id}/audit-events?organisation_id=...`

## Out of scope

Do not implement:

- Audit UI.
- Analytics dashboard.
- Upload.
- Extraction.
- Chunking.
- Embeddings.
- RAG runtime.
- Widget behavior.

## Requirements

- `org_owner` and `client_admin` can read audit events for their organisation/workspace.
- Viewers cannot read audit events in the current RBAC decision.
- Non-members cannot read audit events.
- Cross-tenant audit events are never returned.
- Optional `limit` parameter constrains result count.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-029-audit-event-read-api.md` exists.
- Audit event read schema exists.
- Organisation and workspace audit read endpoints exist.
- Tests cover allowed access, denied access, cross-tenant isolation, viewer decision, and limit behaviour.
- `.ai/CURRENT_SPRINT.md` lists TASK-029 as current task.
- Required validation commands have been run and reported.
