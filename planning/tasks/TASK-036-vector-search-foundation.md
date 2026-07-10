# Task: Vector Search Foundation

## Task ID

TASK-036

## Linked epic/story

- EPIC-003

## Objective

Add tenant-scoped vector similarity search for embedded chunks.

This task adds an internal/manual search endpoint and service foundation only. It does not implement LLM answer generation, prompt assembly, RAG orchestration, widget, analytics, or background queue behaviour.

## Scope

Implement only:

- Vector search service for embedded chunks.
- Required organisation and workspace tenant context.
- Ready chunk and valid active document/version filtering.
- PostgreSQL pgvector similarity search.
- Safe deterministic SQLite fallback for tests.
- Query embedding through the existing embedding provider abstraction.
- Citation-ready result metadata.
- Manual/internal workspace search endpoint.
- Existing development RBAC placeholder checks.
- Tests for tenant search, isolation, membership, viewer access, empty results, and limits.
- Sprint pointer update to TASK-036.

## Endpoint

- `POST /api/v1/workspaces/{workspace_id}/search?organisation_id=...`

Request body:

```json
{
  "query": "When do applications close?",
  "limit": 5
}
```

## Out of scope

Do not implement:

- LLM answer generation.
- Prompt assembly.
- RAG orchestration.
- Widget behaviour.
- Analytics.
- Background queue.

## Requirements

- Search requires `organisation_id` and `workspace_id`.
- Search returns only tenant-scoped ready chunks from ready active document versions and non-deleted documents.
- Viewer access follows the current read RBAC decision and is allowed for organisation members.
- PostgreSQL uses pgvector cosine distance.
- SQLite tests use deterministic local/mock embeddings and cosine similarity.
- Results include score, chunk content, and citation-ready document/version/source metadata.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-036-vector-search-foundation.md` exists.
- Vector search service and endpoint exist.
- Required tenant and result filtering exists.
- Tests cover required success, isolation, authorization, empty, and limit behaviour.
- `.ai/CURRENT_SPRINT.md` lists TASK-036 as current task.
- Required validation commands have been run and reported.
