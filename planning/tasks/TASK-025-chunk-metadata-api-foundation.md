# Task: Chunk Metadata API Foundation

## Task ID

TASK-025

## Linked epic/story

- EPIC-003

## Objective

Add metadata and text read APIs for chunks under tenant-safe document version scope.

This task exposes chunk records only. It does not implement upload, storage, extraction, chunking logic, embeddings, vector search, retrieval, RAG, widget behavior, or analytics.

## Scope

Implement only:

- Chunk response schemas.
- Metadata/text read-only chunk list and read routes under workspace document version paths.
- Tenant-safe repository methods for chunk listing and read.
- Tests for member access, non-member denial, cross-tenant denial, and document/version/workspace scope checks.
- Sprint pointer update to TASK-025.

## Endpoints

- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks?organisation_id=...`
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks/{chunk_id}?organisation_id=...`

## Out of scope

Do not implement:

- Upload.
- Storage.
- Text extraction.
- Chunking logic.
- Embeddings.
- Vector search.
- Retrieval.
- RAG runtime.
- Widget behavior.
- Analytics behavior.

## Requirements

- API routes require explicit `organisation_id` tenant context.
- API routes verify workspace, document, and version belong to the requested tenant scope.
- Routes use repository methods that require organisation, workspace, document, and version context.
- Cross-tenant chunk access returns not found or forbidden without leaking data.
- No chunk creation endpoint is added.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-025-chunk-metadata-api-foundation.md` exists.
- Chunk read schema exists.
- Chunk routes are included under the existing document route module.
- Tests cover own-workspace member access, non-member denial, cross-tenant denial, and document/version scope checks.
- `.ai/CURRENT_SPRINT.md` lists TASK-025 as current task.
- Required validation commands have been run and reported.
