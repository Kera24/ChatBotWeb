# Local Development

Version: 0.1
Status: Foundation

## Purpose

This guide explains how to run the current local development foundation for ChatBotWeb / Yoranix AI Platform.

The current scope is Sprint 0 only:

- FastAPI backend foundation
- Next.js web dashboard foundation
- Static placeholder UI
- No database
- No authentication
- No RAG runtime
- No tenancy implementation
- No Docker yet

## Prerequisites

- Python 3.12 or newer recommended
- Node.js 20 or newer recommended
- npm

Use a Python virtual environment for API work so dependencies stay local to your machine.

## Root Convenience Commands

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
```

These scripts are wrappers around the app-specific commands below.

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

Run API tests from `apps/api`:

```bash
python -m pytest
```

Run database migrations from the repository root:

```bash
npm run api:db:upgrade
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

## Generated Files

Generated local files should not be committed.

Ignored examples:

- Python bytecode and test caches
- Python virtual environments
- Node `node_modules`
- Next.js `.next`
- local environment files
- logs and coverage output

Do not commit `.env` files, API keys, tokens, database passwords, service-role keys, or real client data.

## Docker

Docker is planned later for local development and deployment readiness, but it is not part of TASK-004.

Do not add Docker Compose, database containers, Redis, or object storage until an approved task defines that scope.

## Scope Guardrails

Local development foundation must not introduce product behavior.

Do not add:

- Database models or migrations
- Authentication
- Tenant management
- RAG, embeddings, or AI providers
- Widget runtime
- Real analytics
- Production deployment configuration
