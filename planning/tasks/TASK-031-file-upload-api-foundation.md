# Task: File Upload API Foundation

## Task ID

TASK-031

## Linked epic/story

- EPIC-003

## Objective

Add a tenant-scoped multipart file upload foundation for workspace documents.

This task stores supported files locally, creates document and document-version metadata, and records an upload audit event. It does not implement text extraction, queues, chunking, embeddings, retrieval, RAG, widget, or analytics behaviour.

## Scope

Implement only:

- Multipart file upload endpoint for workspace documents.
- Simple local storage abstraction.
- File type and size validation.
- Supported MVP file types: PDF, DOCX, TXT, and CSV.
- Document record creation.
- Document version record creation.
- Uploaded status on document and document version.
- Tenant-safe `organisation_id` and `workspace_id` checks.
- Existing development RBAC placeholder checks.
- Audit event for document upload.
- Tests for allowed upload, denied viewer, unsupported type, oversized file, cross-tenant denial, created records, and audit event creation.
- Sprint pointer update to TASK-031.

## Endpoint

- `POST /api/v1/workspaces/{workspace_id}/documents/upload?organisation_id=...`

## Out of scope

Do not implement:

- Text extraction.
- Processing queue.
- Chunking.
- Embeddings.
- Retrieval.
- RAG runtime.
- Widget behaviour.
- Analytics.

## Requirements

- `org_owner` and `client_admin` can upload supported files for their organisation workspaces.
- Viewers cannot upload files.
- Non-members cannot upload files.
- Cross-tenant uploads are denied.
- Unsupported file types are rejected.
- Oversized files are rejected when max upload size is configured.
- Upload creates one document and one document version.
- Upload records a tenant-scoped audit event.
- Local file paths are stored as document-version metadata only; no extraction or processing is triggered.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-031-file-upload-api-foundation.md` exists.
- Multipart upload endpoint exists.
- Local storage abstraction exists.
- Supported file validation exists.
- Tenant and RBAC checks are preserved.
- Document and document-version rows are created with uploaded status.
- Audit event is created for successful upload.
- Required tests pass.
- `.ai/CURRENT_SPRINT.md` lists TASK-031 as current task.
