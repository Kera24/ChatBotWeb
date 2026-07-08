# Task: Audit Event Foundation

## Task ID

TASK-028

## Linked epic/story

- EPIC-003

## Objective

Add tenant-scoped audit event foundations and record audit events for document and document-version lifecycle transitions.

This task adds audit persistence and lifecycle logging only. It does not implement analytics dashboards, audit UI, upload, extraction, chunking, embeddings, retrieval, RAG, or widget behavior.

## Scope

Implement only:

- Audit event database model and migration.
- Tenant-safe audit event repository helpers.
- Audit logging for document lifecycle transitions.
- Audit logging for document-version lifecycle transitions.
- Tests that lifecycle transitions create audit events.
- Tests that audit events remain tenant-scoped.
- Sprint pointer update to TASK-028.

## Out of scope

Do not implement:

- Analytics dashboard.
- Audit UI.
- Audit read API.
- Upload.
- Extraction.
- Chunking.
- Embeddings.
- Retrieval.
- RAG runtime.
- Widget behavior.

## Requirements

- Audit events include `organisation_id` and `workspace_id` as first-class columns.
- Lifecycle audit events include action, entity type, entity id, previous status, new status, and safe metadata.
- Audit repository reads require tenant context.
- Lifecycle transition failures do not create audit events.
- Audit read API remains out of scope.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-028-audit-event-foundation.md` exists.
- Audit event model and Alembic migration exist.
- Document and document-version lifecycle transitions create audit events.
- Tests prove audit events are created and tenant-scoped.
- `.ai/CURRENT_SPRINT.md` lists TASK-028 as current task.
- Required validation commands have been run and reported.
