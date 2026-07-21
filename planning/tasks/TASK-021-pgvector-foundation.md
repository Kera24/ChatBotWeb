# Task: pgvector Foundation

## Task ID

TASK-021

## Linked epic/story

- EPIC-001

## Objective

Add local PostgreSQL pgvector support and a safe Alembic migration that enables the `vector` extension for future RAG storage work.

This task prepares database infrastructure only. It does not implement embeddings, chunking, upload, retrieval, RAG, widget behavior, or analytics.

## Scope

Implement only:

- Local PostgreSQL image/configuration that supports pgvector.
- Alembic migration to enable the PostgreSQL `vector` extension safely.
- Documentation for local pgvector usage and verification.
- Migration smoke validation where safe.
- Sprint pointer update to TASK-021.

## Out of scope

Do not implement:

- Embeddings.
- Chunking.
- Upload.
- Retrieval.
- RAG runtime.
- Widget behavior.
- Analytics behavior.

## Requirements

- Docker Compose PostgreSQL can support `CREATE EXTENSION vector` locally.
- Alembic migration is safe for local SQLite fallback and does not break API tests.
- No vector columns are added until document/chunk schema exists in an approved task.
- Local docs explain how to start PostgreSQL and apply the migration.

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

- `planning/tasks/TASK-021-pgvector-foundation.md` exists.
- `docker-compose.yml` uses a PostgreSQL image with pgvector support.
- Alembic has a migration that enables `vector` on PostgreSQL.
- Docs describe the pgvector local development approach.
- `.ai/CURRENT_SPRINT.md` lists TASK-021 as current task.
- Required validation commands have been run and reported.
