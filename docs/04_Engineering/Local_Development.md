# Local Development

Version: 0.5
Status: Foundation

## Purpose

This guide explains how to run the local development foundation for ChatBotWeb / Yoranix AI Platform.

Current local scope:

- FastAPI backend foundation
- Next.js web dashboard foundation
- PostgreSQL with pgvector for future vector search schema
- Redis for future queue and worker tasks
- Docker Compose foundation for local services
- No document upload, workers, RAG runtime, object storage, production Kubernetes, or cloud deployment

## Prerequisites

- Python 3.12 or newer recommended
- Node.js 20 or newer recommended
- npm
- Docker Desktop or Docker Engine with Docker Compose v2

Use a Python virtual environment for API work so dependencies stay local to your machine.

## Environment files

Copy the local example when you want Docker Compose or host commands to use shared defaults:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

The example uses local-only development credentials. Do not commit `.env` files, real passwords, API keys, service-role keys, tokens, or real client data.

## Root convenience commands

From the repository root:

```bash
npm run api:install
npm run api:dev
npm run api:test
npm run api:db:upgrade
npm run web:install
npm run web:dev
npm run web:lint
npm run web:build
npm run verify
```

These scripts are wrappers around the app-specific commands below.

Use `npm run api:test` as the standard API test command from the repository root. Direct `python -m pytest` is intentionally app-local and should be run from `apps/api`, not from the repository root.


## Developer verification

Run the standard local verification from the repository root:

```bash
npm run verify
```

This command runs, in order:

1. `docker compose config`
2. `npm run api:test`
3. `npm run web:lint`
4. `npm run web:build`

The command uses `&&` so it stops on the first failing step and works in common Windows, macOS, and Linux npm shells.

Alembic PostgreSQL verification is separate because it requires Docker PostgreSQL to be running and `DATABASE_URL` to target it:

```powershell
cd apps/api
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
```

## Docker Compose

Validate the Compose file:

```bash
docker compose config
```

Start only PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

Stop the local stack:

```bash
docker compose down
```

Stop the local stack and remove development volumes:

```bash
docker compose down -v
```

Local service URLs:

```text
PostgreSQL: localhost:5432
Redis: localhost:6379
```

Host-machine API commands should use:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb
REDIS_URL=redis://localhost:6379/0
```

The API and web services are optional Compose services behind the `app` profile:

```bash
docker compose --profile app up --build
```

Use the DB/Redis-only command for most foundation database work. The PostgreSQL service uses `pgvector/pgvector:pg16` so migrations can enable the `vector` extension locally.

## API

App path:

```bash
apps/api
```

Install dependencies from the repository root:

```bash
python -m pip install -r apps/api/requirements.txt
```

Or from `apps/api`:

```bash
python -m pip install -r requirements.txt
```

Run the API from `apps/api`:

```bash
uvicorn app.main:app --reload
```

Run API tests from the repository root:

```bash
npm run api:test
```

Run API tests directly from `apps/api`:

```bash
python -m pytest
```

Do not run `python -m pytest` from the repository root unless a future task adds root-level pytest import-path configuration.

Run database migrations from the repository root:

```bash
npm run api:db:upgrade
```

Or from `apps/api`:

```bash
python -m alembic upgrade head
```

When targeting Docker PostgreSQL from `apps/api`, set `DATABASE_URL` first:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
```

Current API verification endpoints:

- `GET /health`
- `GET /api/v1/system/info`

## Web

App path:

```bash
apps/web
```

Install dependencies from the repository root:

```bash
npm --prefix apps/web install
```

Or from `apps/web`:

```bash
npm install
```

Run the web app from `apps/web`:

```bash
npm run dev
```

Run lint from `apps/web`:

```bash
npm run lint
```

Run production build from `apps/web`:

```bash
npm run build
```

Current web routes:

- `/`
- `/knowledge`
- `/chatbot`
- `/analytics`
- `/users`
- `/settings`

## Generated files

Generated local files should not be committed.

Ignored examples:

- Python bytecode and test caches
- Python virtual environments
- Node `node_modules`
- Next.js `.next`
- local environment files
- logs and coverage output
- local SQLite files

Do not commit `.env` files, API keys, tokens, database passwords, service-role keys, or real client data.

## Scope guardrails

Local development foundation must not introduce product behavior.

Do not add without a new approved task:

- Authentication flows
- Document upload
- Ingestion workers
- RAG, embeddings, or AI providers
- Object storage
- Widget runtime
- Production deployment configuration
