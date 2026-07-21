# Task: Docker Compose Foundation

## Task ID

TASK-017

## Linked epic/story

- EPIC-001

## Objective

Add a simple Docker Compose foundation for local development with PostgreSQL and Redis, plus optional API and web services that can use the local stack.

This task implements local development infrastructure only. Keep the setup MVP-focused and avoid production deployment concerns.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `docs/04_Engineering/Local_Development.md`
- `docs/04_Engineering/Database_Local_Setup.md`
- `planning/tasks/TASK-005-database-tenancy-foundation.md`
- `planning/tasks/TASK-012-ingestion-pipeline-design.md`

## Scope

Implement only:

- Docker Compose foundation for local development.
- PostgreSQL service.
- Redis service.
- Optional API service for local development.
- Optional web service for local development.
- Safe environment example files if missing.
- Local development documentation updates.
- Commands for running and validating the stack.

## Out of scope

Do not implement:

- pgvector migration unless already safe and minimal.
- Document upload.
- Workers.
- RAG runtime.
- Object storage.
- Production Kubernetes.
- Cloud deployment.

## Requirements

- Docker Compose supports running PostgreSQL and Redis locally.
- API can use `DATABASE_URL` from environment.
- Redis URL is documented for future worker tasks.
- No secrets are committed.
- Local defaults are safe and development-only.

## Validation commands

Run where possible:

```bash
docker compose config
docker compose up -d postgres redis
python -m pytest
python -m alembic upgrade head
```

## Acceptance criteria

- `docker-compose.yml` exists at repository root.
- PostgreSQL service uses local-only development credentials and a persistent named volume.
- Redis service is available locally for future queue/worker tasks.
- Optional API and web services are documented and do not require production secrets.
- Environment example file documents safe local defaults.
- Local development docs include Docker Compose commands.
- Database local setup docs include PostgreSQL and Redis connection values.
- `.ai/CURRENT_SPRINT.md` lists TASK-017 as current task.
