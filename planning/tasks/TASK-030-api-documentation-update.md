# Task: API Documentation Update

## Task ID

TASK-030

## Linked epic/story

- EPIC-003

## Objective

Update the architecture API specification so it reflects the currently implemented backend endpoints and clearly separates implemented foundation APIs from planned product APIs.

This task updates documentation only. It does not implement code, production authentication, upload, storage, ingestion, retrieval, RAG, chat runtime, analytics, or widget behavior.

## Scope

Implement only:

- Current implemented organisation API documentation.
- Current implemented workspace API documentation.
- Current implemented document metadata API documentation.
- Current implemented document version API documentation.
- Current implemented chunk metadata API documentation.
- Current implemented lifecycle transition API documentation.
- Current implemented audit read API documentation.
- Development-only auth header documentation.
- Workspace-scoped `organisation_id` query requirement documentation.
- Explicit not-implemented notes for upload, storage, ingestion, RAG, and widget endpoints.
- Sprint pointer update to TASK-030.

## Documentation updates

Update:

- `docs/02_Architecture/03_API_Specification.md`
- `.ai/CURRENT_SPRINT.md`

## Out of scope

Do not implement:

- API code changes.
- Database changes.
- Production authentication.
- File upload endpoints.
- Object storage endpoints.
- Document ingestion endpoints.
- Embeddings or retrieval.
- RAG runtime.
- Chat endpoints.
- Widget endpoints.
- Analytics endpoints.

## Requirements

- Document `X-Development-User-Email` and `X-Development-Role` as temporary development-only headers.
- Clearly mark the auth model as a development-only placeholder.
- Document that workspace-scoped routes under `/api/v1/workspaces/{workspace_id}` require `organisation_id` as a query parameter.
- Document only the endpoints currently implemented in the backend.
- Clearly state that upload, storage, ingestion, RAG, and widget endpoints are not implemented yet.

## Validation commands

Run only if documentation changes require additional confidence:

```bash
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-030-api-documentation-update.md` exists.
- API specification reflects current implemented endpoints.
- Development-only auth headers are documented.
- Workspace-scoped `organisation_id` query requirement is documented.
- Planned upload/storage/ingestion/RAG/widget endpoints are marked not implemented.
- `.ai/CURRENT_SPRINT.md` lists TASK-030 as current task.
