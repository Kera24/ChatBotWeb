# Task: Root Test and API DB Hardening

## Task ID

TASK-018

## Linked epic/story

- EPIC-001

## Objective

Clarify and harden local API test and database commands so developers run the supported commands from predictable working directories.

This task keeps the Docker PostgreSQL and Redis workflow intact and avoids adding product behavior.

## Problem

Running `python -m pytest` from the repository root does not put `apps/api` on Python's import path, so API tests fail with `ModuleNotFoundError: No module named 'app'`.

Running the same command from `apps/api` passes.

## Scope

Implement only:

- Root-level npm script guidance for API tests.
- Documentation that identifies `npm run api:test` as the standard root command.
- Documentation that direct `python -m pytest` is an app-local command run from `apps/api`.
- Redis URL configuration placeholder for API settings if missing.
- Sprint pointer update to TASK-018.

## Out of scope

Do not implement:

- Workers.
- Document upload.
- RAG runtime.
- pgvector.
- Widget behavior.
- Analytics behavior.

## Requirements

- `npm run api:test` remains the standard documented API test command from the repository root.
- Developers know exactly where to run API tests and migrations.
- Docker PostgreSQL and Redis commands remain documented.
- API settings include a `REDIS_URL` placeholder for future queue and worker tasks.
- Root-level `python -m pytest` is either supported through config or explicitly documented as intentionally unsupported.

## Validation commands

Run where possible:

```bash
npm run api:test
npm run web:lint
npm run web:build
cd apps/api
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb python -m alembic upgrade head
```

## Acceptance criteria

- `planning/tasks/TASK-018-root-test-and-api-db-hardening.md` exists.
- `.ai/CURRENT_SPRINT.md` lists TASK-018 as current task.
- Local development docs explain root and app-local API test commands.
- Database setup docs explain app-local Alembic execution and root npm wrapper usage.
- API settings expose `REDIS_URL` with a local development default.
- Required validation commands have been run and reported.
