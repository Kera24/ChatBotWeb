# ChatBotWeb / Yoranix AI Platform

A multi-tenant AI knowledge platform for building, deploying, and managing client-specific RAG chatbots and AI assistants.

This repository is being structured as a production SaaS platform, not a one-off chatbot demo. The long-term goal is to support thousands of organisations, each with its own secure workspace, knowledge base, chatbot widget, analytics, integrations, and future AI agents.

## Product vision

Build once. Deploy AI everywhere.

The platform should allow a client to:

1. Create an organisation workspace.
2. Upload documents, FAQs, policies, URLs, and other knowledge sources.
3. Automatically process and index that knowledge.
4. Deploy a branded chatbot to their website.
5. Continuously update knowledge without developer involvement.
6. Review analytics, unanswered questions, and user feedback.

## Target users

- Colleges and RTOs
- Education consultancies
- Migration agencies
- Healthcare clinics
- Professional service firms
- Hospitality businesses
- Internal business teams

## Initial architecture direction

- Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui
- Backend API: FastAPI, Python
- Database: PostgreSQL
- Vector search: pgvector first, Qdrant later when needed
- AI orchestration: LangGraph and LlamaIndex
- Object storage: S3-compatible storage or MinIO
- Queue: Redis and Celery
- Deployment: Docker first, Kubernetes later

## Repository structure

```text
apps/
  web/              # Public marketing site and client-facing dashboard
  admin/            # Super-admin dashboard
  widget/           # Embeddable website chatbot widget
  api/              # API application entrypoint

services/
  ingestion-service/
  rag-service/
  agent-service/
  evaluation-service/

packages/
  ui/
  types/
  prompts/
  sdk/

docs/
  00_Project_Charter/
  01_Product/
  02_Architecture/
  03_AI/
  04_Engineering/
  05_Design/
  06_Security/
  07_Roadmap/
  adr/
```

## Current phase

Phase 1: research, product definition, technical architecture, and implementation planning.

No production feature should be built until the MVP requirements, architecture, database model, API design, and RAG pipeline design are documented.

## Local development

Start here:

- Local development guide: `docs/04_Engineering/Local_Development.md`
- Database local setup: `docs/04_Engineering/Database_Local_Setup.md`
- API app: `apps/api/README.md`
- Web app: `apps/web/README.md`

Common root commands:

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

Current foundation scope does not include database, authentication, RAG, tenancy, or Docker.

## Engineering principle

Every feature must answer three questions:

1. Does it reduce repeated implementation work for new clients?
2. Can it scale to thousands of client workspaces?
3. Can clients manage it without developer involvement?

If the answer is no, redesign the feature.

## Widget SDK Foundation

The repository includes `packages/widget-sdk`, a private TypeScript package foundation for the future embeddable Yoranix widget loader. It currently provides typed configuration validation, environment resolution, version constants, safe SDK error contracts, ESM/IIFE builds, declarations, and tests.

It does not yet mount an iframe, call public APIs, store sessions, expose `window.YoranixWidget`, implement postMessage, or render widget UI.

Root commands:

```bash
npm run widget-sdk:install
npm run widget-sdk:test
npm run widget-sdk:lint
npm run widget-sdk:build
```
