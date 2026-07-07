# Architecture Context

Primary source: `docs/02_Architecture/01_System_Architecture.md`

Related sources:

- `docs/02_Architecture/02_Database_Design.md`
- `docs/02_Architecture/03_API_Specification.md`
- `docs/adr/0001-platform-architecture.md`
- `implementation-pack/README.md`

## Architecture goal

Build a modular multi-tenant SaaS platform that supports client-specific knowledge bases, RAG chatbots, website widgets, analytics, and future AI agents.

## Core boundaries

- `apps/web` - client-facing dashboard and future public marketing site
- `apps/admin` - internal super-admin interface
- `apps/widget` - embeddable chatbot widget
- `apps/api` - main API entrypoint
- `services/ingestion-service` - extraction, chunking, metadata, processing
- `services/rag-service` - retrieval, context assembly, generation, citations
- `services/agent-service` - future tool-using agents
- `services/evaluation-service` - answer and retrieval quality
- `packages/` - shared UI, types, prompts, SDK, and reusable code

## Data stores

- PostgreSQL is the primary relational database.
- pgvector is the MVP vector store.
- Object storage stores uploaded files and processed artifacts.
- Redis supports queues, caching, rate limits, and short-lived runtime state.

## Non-negotiable architecture rules

- No cross-tenant retrieval.
- No answer without tenant context.
- Long-running work must use queues.
- Uploaded files must not be processed synchronously in request-response paths.
- AI calls must be logged for cost, latency, and quality once implemented.
- Public widget endpoints must be rate-limited and domain-aware.

## Architecture change rule

Do not change architecture casually. If a task requires a new service, data store, framework, dependency, or cross-cutting pattern, document the reason and consider an ADR.
