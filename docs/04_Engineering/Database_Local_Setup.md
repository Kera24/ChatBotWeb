# Database Local Setup

Version: 0.6
Status: Foundation

## Purpose

This guide explains the local database foundation for database and tenancy work.

Current scope:

- SQLAlchemy setup
- Alembic migration setup
- Organisation, workspace, user, and membership models
- Tenant isolation repository patterns
- PostgreSQL local development through Docker Compose
- Redis local development endpoint for future queue and worker tasks
- pgvector extension support for future vector search schema

It does not include authentication, login, invitation flows, RAG, document upload, widget runtime, analytics, billing, object storage, workers, production Kubernetes, or cloud deployment.

## Database choice

The MVP target database is PostgreSQL.

Local Docker Compose uses `pgvector/pgvector:pg16` so PostgreSQL can enable the `vector` extension. This task enables the extension only; vector columns are deferred until document chunk schema is introduced by an approved task.

The API configuration also defaults to a local SQLite file at `apps/api/local.db` when `DATABASE_URL` is not set. This fallback exists only so foundation migrations can be smoke-tested without Docker or a provisioned PostgreSQL instance.

## Docker Compose services

Start local PostgreSQL and Redis from the repository root:

```bash
docker compose up -d postgres redis
```

Validate the Compose configuration:

```bash
docker compose config
```

Stop services:

```bash
docker compose down
```

Remove local development volumes as well:

```bash
docker compose down -v
```

## pgvector local support

The local PostgreSQL service runs an image with pgvector installed. Apply migrations after starting PostgreSQL to enable the extension in the local database:

```powershell
docker compose up -d postgres redis
cd apps/api
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
```

On bash-like shells:

```bash
docker compose up -d postgres redis
cd apps/api
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb python -m alembic upgrade head
```

The pgvector foundation migration runs `CREATE EXTENSION IF NOT EXISTS vector` only for PostgreSQL. SQLite fallback migrations skip this extension so API tests remain lightweight.

## Environment variables

Copy the example file for local overrides:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Host-machine PostgreSQL URL:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb
```

Docker Compose API service PostgreSQL URL:

```bash
API_DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/chatbotweb
```

Redis URL for future worker and queue tasks:

```bash
REDIS_URL=redis://localhost:6379/0
```

Use local-only credentials. Do not commit `.env` files, passwords, service-role keys, API keys, tokens, or real client data.

## Install API dependencies

From the repository root:

```bash
npm run api:install
```

Or directly:

```bash
python -m pip install -r apps/api/requirements.txt
```

## Run migrations

From the repository root, use the npm wrapper:

```bash
npm run api:db:upgrade
```

From `apps/api`:

```bash
python -m alembic upgrade head
```

With `DATABASE_URL` unset, this creates or updates `apps/api/local.db`.

With `DATABASE_URL` set, this applies migrations to that database.

For PostgreSQL via Docker Compose, start PostgreSQL first, then run:

```bash
cd apps/api
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
```

On bash-like shells:

```bash
cd apps/api
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb python -m alembic upgrade head
```

## Run tests

From the repository root:

```bash
npm run api:test
```

This is the standard root command. Direct `python -m pytest` is intentionally supported from `apps/api` only:

```bash
cd apps/api
python -m pytest
```

Do not run `python -m pytest` from the repository root unless root-level pytest configuration is added in a future task.

The database model tests use in-memory SQLite. They verify model creation and tenant isolation query patterns without requiring a local PostgreSQL server.


## Document and chunk schema

The document schema foundation creates three tenant-scoped tables:

- `documents`: stable source identity inside one organisation and workspace.
- `document_versions`: immutable processable snapshots of a document.
- `chunks`: retrievable text units tied to one document version.

All three tables carry tenant context columns where needed for safe filtering. Repository access must include `organisation_id` and `workspace_id`; do not fetch documents by `document_id` alone or chunks by `chunk_id` alone.

The chunk table includes a nullable `embedding_vector` column using pgvector for future embedding tasks. TASK-022 does not generate embeddings, run vector search, or add vector indexes.

## Tenant isolation rules

- Do not fetch workspace-scoped records by ID alone.
- Workspace-scoped queries must include `organisation_id` and `workspace_id`.
- Organisation-scoped queries must include `organisation_id`.
- Future tenant-owned tables must include `organisation_id` or `workspace_id` as required.
- Repository functions should make missing tenant context hard to express.

## Current migration

Current migrations:

```text
0001_create_tenant_foundation
0002_enable_pgvector_extension
0003_doc_chunk_schema
```

`0001_create_tenant_foundation` creates:

- `organisations`
- `workspaces`
- `users`
- `memberships`
