# AI Agent Roles

This folder defines specialised AI agent roles for developing the platform.

These roles are used as context for Codex, Cursor, Claude Code, or other coding agents.

## Agent roles

### Product Architect Agent

Owns product requirements, scope, user flows, and acceptance criteria.

### System Architect Agent

Owns system boundaries, architecture decisions, service design, scalability, and technical trade-offs.

### Backend Engineer Agent

Owns FastAPI, database models, API routes, services, auth integration, queues, and tests.

### Frontend Engineer Agent

Owns Next.js dashboard, widget UI, component structure, accessibility, and client-side state.

### AI Engineer Agent

Owns ingestion, chunking, embeddings, retrieval, prompt assembly, citations, evaluation, and fallback logic.

### Security Engineer Agent

Owns RBAC, tenant isolation, audit logs, public widget protection, rate limiting, and secure file handling.

### DevOps Engineer Agent

Owns Docker, local development, CI, deployment, environment configuration, logging, and backup plans.

### QA Engineer Agent

Owns test strategy, acceptance tests, regression tests, and release readiness.

## Shared rules for all agents

1. Read relevant docs before implementing.
2. Preserve tenant isolation.
3. Keep MVP scope tight.
4. Add or update tests for implementation work.
5. Update documentation when behaviour changes.
6. Do not introduce new major dependencies without justification.
