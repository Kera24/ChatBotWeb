# Task: Chunking Foundation

## Task ID

TASK-034

## Linked epic/story

- EPIC-003

## Objective

Add a tenant-scoped chunking foundation for extracted text artifacts.

This task reads extracted text from a document version, creates MVP chunk records, and exposes a manual API trigger. It does not implement embeddings, vector search, retrieval, RAG, widget, analytics, or background queue behaviour.

## Scope

Implement only:

- Chunking service for extracted text artifacts.
- Local storage read from `document_versions.extracted_text_path`.
- Simple word-aware MVP chunking.
- Configurable chunk size.
- Configurable overlap.
- Stable `chunk_index` preservation.
- Source metadata preservation on chunk rows.
- Chunk creation for a document version.
- Manual chunking API endpoint.
- Existing development RBAC placeholder checks.
- Tenant-safe organisation/workspace/document/version checks.
- Audit events for chunking success and failure.
- Tests for success, viewer denial, cross-tenant denial, invalid status, missing extracted text path, and repeated chunking.
- Sprint pointer update to TASK-034.

## Endpoint

- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunk?organisation_id=...`

## Out of scope

Do not implement:

- Embeddings.
- Vector search.
- Retrieval.
- RAG runtime.
- Widget behaviour.
- Analytics.
- Background queue.

## Requirements

- Only `ready` document versions can be chunked.
- Document versions must have `extracted_text_path`.
- Repeated chunking is safely rejected when chunks already exist.
- Created chunks preserve tenant, document, version, source type, title, strategy version, index, content hash, and approximate token count.
- Audit events are written for chunking success and failure.
- File paths remain constrained to configured local storage.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-034-chunking-foundation.md` exists.
- Chunking service exists.
- Manual chunking endpoint exists.
- Tests cover required success and denial/failure paths.
- `.ai/CURRENT_SPRINT.md` lists TASK-034 as current task.
- Required validation commands have been run and reported.
