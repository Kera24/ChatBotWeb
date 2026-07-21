# Task: Document Lifecycle Status Transitions

## Task ID

TASK-026

## Linked epic/story

- EPIC-003

## Objective

Add metadata-only lifecycle transition methods for documents and document versions with tenant-safe access and transition validation.

This task adds lifecycle state foundations only. It does not implement upload, file storage, extraction, chunking, embeddings, vector search, retrieval, RAG, widget behavior, or analytics.

## Scope

Implement only:

- Document status transition service/repository methods.
- Document version processing-status transition service/repository methods.
- Validation for allowed and invalid transitions.
- Tenant-safe document/version access during transitions.
- Tests for valid transitions, invalid transitions, cross-tenant denial, and archived/expired behaviour.
- Sprint pointer update to TASK-026.

## Supported transitions

Documents:

- `uploaded -> processing`
- `processing -> ready`
- `processing -> failed`
- `ready -> archived`
- `ready -> expired`

Document versions:

- `pending -> queued`
- `queued -> extracting`
- `extracting -> chunking`
- `chunking -> embedding`
- `embedding -> ready`
- `extracting -> failed`
- `chunking -> failed`
- `embedding -> failed`
- `ready -> superseded`

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

- Transition methods require `organisation_id`, `workspace_id`, and relevant IDs.
- Invalid transitions raise a clear domain error.
- Cross-tenant transition attempts do not mutate records.
- Archived and expired documents are terminal for this task.
- Failed versions can store safe processing error text.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-026-document-lifecycle-status-transitions.md` exists.
- Lifecycle transition methods exist for documents and document versions.
- Tests cover valid transitions, invalid transitions, cross-tenant denial, and archived/expired terminal behaviour.
- `.ai/CURRENT_SPRINT.md` lists TASK-026 as current task.
- Required validation commands have been run and reported.
