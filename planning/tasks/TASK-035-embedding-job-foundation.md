# Task: Embedding Job Foundation

## Task ID

TASK-035

## Linked epic/story

- EPIC-003

## Objective

Add a manual, tenant-scoped embedding foundation for ready chunks.

This task adds an embedding service abstraction, deterministic local/mock provider, and manual API trigger. It does not implement vector search, retrieval, RAG, widget, analytics, or background queue behaviour.

## Scope

Implement only:

- Embedding service abstraction.
- Deterministic local/mock embedding provider for tests and development.
- Manual endpoint to embed ready chunks.
- Postgres/pgvector-aware `embedding_vector` persistence when available.
- Tenant-safe organisation/workspace/document/version checks.
- Existing development RBAC placeholder checks.
- Embedding provider and dimension config.
- Audit events for embedding success and failure.
- Tests for successful embedding, viewer denial, cross-tenant denial, invalid version/chunk state, and provider failure.
- Sprint pointer update to TASK-035.

## Endpoint

- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/embed?organisation_id=...`

## Out of scope

Do not implement:

- Vector search.
- Retrieval.
- RAG runtime.
- Widget behaviour.
- Analytics.
- Background queue.

## Requirements

- Only `ready` document versions can be embedded.
- Only `ready` chunks are eligible for embedding.
- Missing or invalid chunk state is safely rejected.
- Provider failures are handled safely and audited.
- Local/mock embeddings are deterministic.
- `embedding_vector` is stored only when the database dialect supports Postgres/pgvector storage.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-035-embedding-job-foundation.md` exists.
- Embedding service abstraction exists.
- Manual embedding endpoint exists.
- Tests cover required success and denial/failure paths.
- `.ai/CURRENT_SPRINT.md` lists TASK-035 as current task.
- Required validation commands have been run and reported.
