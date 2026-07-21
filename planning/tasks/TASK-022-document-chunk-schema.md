# Task: Document Chunk Schema

## Task ID

TASK-022

## Linked epic/story

- EPIC-003

## Objective

Add tenant-safe database schema, models, and repository access patterns for documents, document versions, and chunks.

This task creates persistence foundations only. It does not implement upload, storage, extraction, chunking, embeddings, vector search, RAG, widget behavior, or analytics.

## Scope

Implement only:

- Database models and migration for `documents`, `document_versions`, and `chunks`.
- Tenant-safe fields on knowledge records.
- Lifecycle/status fields from TASK-011.
- Metadata fields from TASK-014.
- Indexes for tenant, workspace, status, and version filtering.
- Repository functions that require tenant/workspace context.
- Tests for tenant-safe document and chunk access.
- Sprint pointer update to TASK-022.

## Out of scope

Do not implement:

- Upload API.
- File storage.
- Text extraction.
- Chunking logic.
- Embeddings generation.
- Vector search.
- RAG runtime.
- Widget behavior.
- Analytics behavior.

## Requirements

- Documents belong to one organisation and one workspace.
- Document versions belong to one document and keep tenant columns for scoped queries.
- Chunks belong to one organisation, one workspace, one document, and one document version.
- Repository reads never fetch by `document_id` or `chunk_id` alone.
- Chunk schema includes a nullable pgvector-backed `embedding_vector` placeholder for future embedding tasks.
- Tenant isolation tests cover wrong-organisation and wrong-workspace lookups.

## Validation commands

Run:

```bash
docker compose up -d postgres redis
cd apps/api
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
cd ../..
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-022-document-chunk-schema.md` exists.
- Alembic migration creates `documents`, `document_versions`, and `chunks`.
- SQLAlchemy models represent the new schema.
- Tenant-safe repository functions require organisation and workspace context.
- Tests prove document/chunk reads do not cross tenant boundaries.
- `.ai/CURRENT_SPRINT.md` lists TASK-022 as current task.
- Required validation commands have been run and reported.
