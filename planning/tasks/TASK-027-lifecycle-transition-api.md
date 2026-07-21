# Task: Lifecycle Transition API

## Task ID

TASK-027

## Linked epic/story

- EPIC-003

## Objective

Expose metadata-only API endpoints for document and document-version lifecycle transitions using the existing tenant-safe lifecycle service.

This task adds API wrappers only. It does not implement upload, file storage, extraction, chunking, embeddings, retrieval, RAG, widget behavior, or analytics.

## Scope

Implement only:

- Request schemas for lifecycle transitions.
- Document lifecycle transition endpoint.
- Document version lifecycle transition endpoint.
- Existing development auth/RBAC placeholder checks.
- Tenant-safe organisation, workspace, document, and version access.
- Tests for manager access, viewer denial, invalid transitions, cross-tenant denial, and terminal archive/expiry behaviour.
- Sprint pointer update to TASK-027.

## Endpoints

- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/transition?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/transition?organisation_id=...`

## Request body

- `target_status`
- `error_message` optional for failed state

## Out of scope

Do not implement:

- Upload.
- File storage.
- Text extraction.
- Chunking.
- Embeddings.
- Vector search.
- Retrieval.
- RAG runtime.
- Widget behavior.
- Analytics behavior.

## Requirements

- API routes require explicit `organisation_id` tenant context.
- API routes require manager roles through the existing RBAC placeholder.
- Invalid lifecycle transitions return a clear `400` error.
- Cross-tenant transition attempts return not found or forbidden without leaking data.
- Archived and expired document terminal behaviour remains enforced by the lifecycle service.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-027-lifecycle-transition-api.md` exists.
- Transition request schema exists.
- Document and document-version transition routes exist.
- Tests cover manager access, viewer denial, invalid transition errors, cross-tenant denial, and terminal archive/expiry behaviour.
- `.ai/CURRENT_SPRINT.md` lists TASK-027 as current task.
- Required validation commands have been run and reported.
