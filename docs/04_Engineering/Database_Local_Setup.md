# Database Local Setup

Version: 0.1
Status: Foundation

## Purpose

This guide explains the local database foundation for TASK-005.

The current scope is limited to:

- SQLAlchemy setup
- Alembic migration setup
- Organisation, workspace, user, and membership models
- Tenant isolation repository patterns

It does not include authentication, login, invitation flows, RAG, document upload, widget runtime, analytics, billing, or Docker.

## Database choice

The MVP target database is PostgreSQL.

The API configuration also defaults to a local SQLite file at `apps/api/local.db` when `DATABASE_URL` is not set. This default exists only so the foundation migration can be smoke-tested without Docker or a provisioned PostgreSQL instance.

## Environment variable

Set `DATABASE_URL` for PostgreSQL:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb
```

Use local-only credentials. Do not commit `.env` files, passwords, service-role keys, API keys, or real client data.

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

From `apps/api`:

```bash
python -m alembic upgrade head
```

With `DATABASE_URL` unset, this creates or updates `apps/api/local.db`.

With `DATABASE_URL` set, this applies migrations to that database.

## Run tests

From the repository root:

```bash
npm run api:test
```

The database model tests use in-memory SQLite. They verify model creation and tenant isolation query patterns without requiring a local PostgreSQL server.

## Tenant isolation rules

- Do not fetch workspace-scoped records by ID alone.
- Workspace-scoped queries must include `organisation_id` and `workspace_id`.
- Organisation-scoped queries must include `organisation_id`.
- Future tenant-owned tables must include `organisation_id` or `workspace_id` as required.
- Repository functions should make missing tenant context hard to express.

## Current migration

Initial migration:

```text
0001_create_tenant_foundation
```

Creates:

- `organisations`
- `workspaces`
- `users`
- `memberships`
