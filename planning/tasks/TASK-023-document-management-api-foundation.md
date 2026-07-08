# Task: Document Management API Foundation

## Task ID

TASK-023

## Linked epic/story

- EPIC-003

## Objective

Add metadata-only document management API endpoints backed by tenant-safe document repository methods.

This task creates API foundations only. It does not implement upload, object storage, extraction, chunking, embeddings, retrieval, RAG, widget behavior, or analytics.

## Scope

Implement only:

- Document API schemas.
- Metadata-only document list, create, and read routes under workspace paths.
- Existing development auth/RBAC placeholder checks.
- Tenant-safe repository usage.
- Tests for allowed access, denied access, and tenant isolation.
- Sprint pointer update to TASK-023.

## Endpoints

- `GET /api/v1/workspaces/{workspace_id}/documents?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/documents?organisation_id=...`
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}?organisation_id=...`

## Out of scope

Do not implement:

- Multipart upload.
- Object storage.
- Text extraction.
- Chunking.
- Embeddings.
- Retrieval.
- RAG runtime.
- Widget behavior.
- Analytics behavior.

## Requirements

- API routes require explicit `organisation_id` tenant context.
- API routes verify the workspace belongs to the organisation.
- List/read routes allow viewer-level organisation members.
- Create route allows `org_owner` and `client_admin` members.
- Routes use repository methods that require organisation and workspace context.
- Cross-tenant document access returns not found or forbidden without leaking data.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-023-document-management-api-foundation.md` exists.
- Document create/read schemas exist.
- Document routes are included in the API router.
- Tests cover create, list, read, denied role access, and tenant isolation.
- `.ai/CURRENT_SPRINT.md` lists TASK-023 as current task.
- Required validation commands have been run and reported.
