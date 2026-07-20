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
npm run web:test
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
3. `npm run web:test`
4. `npm run web:lint`
5. `npm run web:build`

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

Run tests from `apps/web`:

```bash
npm run test:run
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
- `/conversations`
- `/conversations/[conversationId]`
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

## Widget SDK Foundation

The repository includes a standalone SDK package foundation at `packages/widget-sdk`.

Root commands:

```bash
npm run widget-sdk:install
npm run widget-sdk:test
npm run widget-sdk:lint
npm run widget-sdk:build
```

`npm run verify` includes the SDK test, lint, and build steps after API and web verification.

The SDK package currently defines configuration validation, environment resolution, version constants, and safe error contracts only. It does not mount an iframe, call public APIs, store sessions, expose the final global lifecycle API, or render widget UI.

## Widget Iframe Shell

The repository includes a dedicated iframe shell app at `apps/widget` for the future embeddable widget. It is separate from the dashboard web app and currently implements only bootstrap, parent-origin validation, shared postMessage protocol validation, and neutral loading/ready/unavailable shell states.

Root commands:

```bash
npm run widget:install
npm run widget:test
npm run widget:lint
npm run widget:build
```

`npm run verify` includes widget app tests, lint, and build after API, web, and SDK checks.

The widget app does not call public APIs, store sessions, render chat UI, or expose the final global SDK lifecycle API.

## Widget Iframe API Client

The widget iframe app now owns public config/session/message API calls and session storage. Session tokens remain inside the iframe origin and are not exposed through the SDK runtime or postMessage.

Additional reference:

- `docs/04_Engineering/Widget_Iframe_API_Client_and_Session_Storage.md`

## Widget Browser Tests

The repository includes Playwright browser integration/security tests for the embeddable widget.

```bash
npm run widget:e2e:install
npm run widget:e2e:chromium
npm run widget:e2e:extended
```

`npm run verify` runs the Chromium suite and then rebuilds the production widget artifact. The tests use fake widget keys and local mock endpoints only.

### Widget rendering foundation

The widget iframe now has a Preact-based structural shell and design-token system. Preact is isolated to `apps/widget`; the loader SDK remains framework-free. Current UI scope is launcher/panel/header/status/viewport/footer only.

Useful commands:

```bash
npm run widget:test
npm run widget:build
npm run widget:e2e:chromium
```

## Widget B2 Conversation Shell

Run
pm run widget:dev from the root equivalent via
pm --prefix apps/widget run dev for the iframe app, or use
pm run widget:e2e:chromium to exercise the loader, iframe, mock API, suggested-question send flow, and token-isolation checks.

### Widget composer and citation checks

TASK-065B3 browser coverage is included in the widget e2e commands:

```bash
npm run widget:e2e:chromium
npm run widget:e2e:extended
```

The tests use fake widget keys and local mock API responses for composer, citation, rate-limit, and invalid-session scenarios.
## Widget Release Verification

TASK-065B4 adds release-readiness commands for the embeddable widget:

```bash
npm run widget:inspect:production
npm run widget:bundle:check
npm run widget:e2e:a11y
npm run widget:e2e:visual
npm run widget:e2e:visual:update
npm run widget:release:verify
```

Run `npm run widget:build` before `npm run widget:inspect:production`; test-mode builds intentionally include browser-test hooks and should not be inspected as production artifacts.
## Widget release artifact commands

TASK-066B1 adds local, provider-neutral release artifact preparation. These commands do not deploy anything:

```bash
npm run widget:config:validate
npm run widget:release:build
npm run widget:e2e:release
```

The generated output is ignored under `artifacts/widget-release/`. Production-like validation requires HTTPS origin-only values for `WIDGET_PUBLIC_ORIGIN`, `WIDGET_PUBLIC_API_ORIGIN`, and `WIDGET_SDK_PUBLIC_ORIGIN`; CI defaults use safe placeholder origins.

## Widget Pilot Verification

Run the synthetic real-backend pre-pilot gate with:

```bash
npm run widget:pilot:verify
```

The command uses synthetic test data only and writes a safe report to `artifacts/widget-pilot-verification/report.json`.

## TASK-066B3 Operational Controls

TASK-066B3 adds provider-neutral operational controls for controlled pilot readiness: `/health/live`, `/health/ready`, safe request correlation IDs, privacy-preserving redaction helpers, in-memory operational counters for test evidence, server-side pilot allowlist controls, global/widget/message kill switches, provider-neutral alert definitions, a dry-run rollback planner, and `npm run widget:pilot:readiness`. It does not deploy production infrastructure or add a monitoring vendor.
