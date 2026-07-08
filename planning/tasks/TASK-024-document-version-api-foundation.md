# Task: Document Version API Foundation

## Task ID

TASK-024

## Linked epic/story

- EPIC-003

## Objective

Add metadata-only document version read APIs backed by tenant-safe repository methods.

This task exposes version metadata only. It does not implement file upload, storage, extraction, chunking, embeddings, retrieval, RAG, widget behavior, or analytics.

## Scope

Implement only:

- Document version API schemas.
- Metadata-only document version list and read routes under workspace document paths.
- Tenant-safe repository methods for version listing and read.
- Tests for member access, non-member denial, cross-tenant denial, and document/workspace scope checks.
- Sprint pointer update to TASK-024.

## Endpoints

- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions?organisation_id=...`
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}?organisation_id=...`

## Out of scope

Do not implement:

- File upload.
- Storage.
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
- API routes verify the document belongs to the requested organisation and workspace.
- Routes use repository methods that require organisation, workspace, and document context.
- Cross-tenant version access returns not found or forbidden without leaking data.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-024-document-version-api-foundation.md` exists.
- Document version read schema exists.
- Version routes are included under the existing document route module.
- Tests cover own-workspace member access, non-member denial, cross-tenant denial, and document/workspace scope checks.
- `.ai/CURRENT_SPRINT.md` lists TASK-024 as current task.
- Required validation commands have been run and reported.
