# Task: Manual Extraction Pipeline Integration

## Task ID

TASK-033

## Linked epic/story

- EPIC-003

## Objective

Add a manual, tenant-scoped extraction trigger for a document version.

This task wires the existing upload metadata and text extraction service together through an explicit service call and API endpoint. It does not implement background processing, chunking, embeddings, vector search, retrieval, RAG, widget, or analytics behaviour.

## Scope

Implement only:

- Manual extraction service for one document version.
- Local storage read from `document_versions.original_file_path`.
- Existing text extraction service integration.
- Extracted text artifact storage.
- Document-version status updates for `uploaded -> processing -> ready`.
- Document-version status updates for `uploaded -> processing -> failed`.
- Manual extraction API endpoint.
- Existing development RBAC placeholder checks.
- Tenant-safe organisation/workspace/document/version checks.
- Audit events for extraction success and failure.
- Tests for success, parser failure, viewer denial, cross-tenant denial, and invalid status.
- Sprint pointer update to TASK-033.

## Endpoint

- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/extract?organisation_id=...`

## Out of scope

Do not implement:

- Background queue.
- Chunking.
- Embeddings.
- Vector search.
- Retrieval.
- RAG runtime.
- Widget behaviour.
- Analytics.

## Requirements

- Only `uploaded` document versions can be manually extracted.
- Successful extraction stores an extracted text artifact and sets status to `ready`.
- Failed extraction records a safe error and sets status to `failed`.
- Extraction failures are structured and do not crash the API.
- Audit events are written for extraction success and failure.
- File paths remain constrained to configured local storage.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-033-manual-extraction-pipeline-integration.md` exists.
- Manual extraction service exists.
- Manual extraction endpoint exists.
- Status transitions are implemented for success and failure.
- Extracted text artifact path is stored on the document version.
- Tests cover success, parser failure, viewer denial, cross-tenant denial, and invalid status.
- `.ai/CURRENT_SPRINT.md` lists TASK-033 as current task.
- Required validation commands have been run and reported.
