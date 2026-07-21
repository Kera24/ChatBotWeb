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

## Widget Iframe Shell

The repository includes `apps/widget`, a dedicated Vite TypeScript iframe shell for the future embeddable widget. It consumes shared protocol contracts from `packages/widget-sdk`, validates the parent-origin bootstrap, performs the initial secure postMessage handshake, and renders only neutral loading/ready/unavailable states.

Root commands:

```bash
npm run widget:install
npm run widget:test
npm run widget:lint
npm run widget:build
```

It does not call public APIs, store sessions, render chat UI, or expose the final `window.YoranixWidget` API.

## Widget SDK Lifecycle Runtime

TASK-064B3 adds lifecycle and mounting support to `packages/widget-sdk` plus a local smoke host under `examples/widget-host`.

Additional root commands remain:

```bash
npm run widget-sdk:test
npm run widget-sdk:lint
npm run widget-sdk:build
npm run widget:test
npm run widget:lint
npm run widget:build
```

The browser bundle now installs `window.YoranixWidget` when safe and supports the approved lifecycle methods. It still does not call public APIs, store sessions, render the final widget UI, or send messages.

## Widget Iframe API Client

`apps/widget` now contains the iframe-owned public API client and session storage foundation. It loads public configuration after handshake, caches config with ETag support, stores anonymous session tokens only in iframe-origin `sessionStorage` or memory fallback, and has an internal message service for future UI integration.

The host SDK cannot send messages itself and never receives a public session token.

## Widget Browser Security Tests

TASK-064B5 adds Playwright browser tests under `tests/widget-browser`. The required Chromium suite is part of `npm run verify`; the extended Firefox/WebKit suite is available with `npm run widget:e2e:extended`.

### Widget UI foundation

TASK-065B1 adds the Preact-based iframe visual shell and design-token foundation. The shell does not yet include welcome content, messages, composer, citations, or final visual polish.

```bash
npm run widget:test
npm run widget:e2e:chromium
```

### Widget TASK-065B2

The widget iframe now includes the welcome and in-memory conversation presentation layer. Suggested questions can send through the iframe-owned API client; free-text composer and citation disclosure are still deferred.

### Widget TASK-065B3

The widget iframe now supports free-text conversation, citation disclosure, privacy footer, and recovery notices. It still excludes Markdown, streaming, persisted history, uploads, voice, lead capture, telemetry, and backend changes.
### Widget TASK-065B4

The widget iframe now has responsive/mobile hardening, controlled motion refinements, accessibility and visual-regression browser suites, production bundle inspection, and release-readiness documentation. The current release classification is controlled pilot readiness. General availability still requires production-domain setup, real-backend smoke coverage, operational monitoring, and manual assistive-technology review.

Additional commands:

```bash
npm run widget:inspect:production
npm run widget:bundle:check
npm run widget:e2e:a11y
npm run widget:e2e:visual
npm run widget:e2e:visual:update
npm run widget:release:verify
```
## Widget Production Delivery

TASK-066B1 adds provider-neutral widget release artifact generation and delivery policy. It does not deploy production infrastructure.

```bash
npm run widget:config:validate
npm run widget:release:build
npm run widget:e2e:release
```

Generated release output is ignored under `artifacts/widget-release/`. See `docs/04_Engineering/Widget_Production_Delivery_Security_and_Versioning.md` and `docs/06_Operations/Widget_Deployment_Runbook.md`.

## Widget Pilot Verification

Before controlled pilot deployment, run:

```bash
npm run widget:pilot:verify
```

This validates release artifacts and runs the synthetic real-backend config/session/message and tenant-isolation smoke suite. It does not deploy production infrastructure.

## TASK-066B3 Operational Controls

TASK-066B3 adds provider-neutral operational controls for controlled pilot readiness: `/health/live`, `/health/ready`, safe request correlation IDs, privacy-preserving redaction helpers, in-memory operational counters for test evidence, server-side pilot allowlist controls, global/widget/message kill switches, provider-neutral alert definitions, a dry-run rollback planner, and `npm run widget:pilot:readiness`. It does not deploy production infrastructure or add a monitoring vendor.

## Widget Administration Revisioning

Backend widget administration revisioning is documented in `docs/04_Engineering/Widget_Administration_Revisioning_and_Publishing.md`. TASK-067B1 adds server APIs and database revisioning only; admin UI, embed management, public-key rotation, and preview grants remain deferred.

## Widget Origins, Public Key, And Embed Management

TASK-067B2 adds backend APIs for widget allowed origins, immediate public-key rotation, approved SDK embed-version preferences, supported-version listing, and safe embed snippet metadata. See `docs/04_Engineering/Widget_Origins_Public_Key_and_Embed_Management.md`.

Admin UI, preview grants, installation verification, and production deployment remain deferred.

## Widget Administration Frontend

TASK-067B3 adds authenticated dashboard routes for widget list, creation, draft settings, allowed domains, embed setup, SDK version selection, and public-key rotation. See `docs/04_Engineering/Widget_Administration_Frontend_Settings_Domains_and_Embed.md`.

Publish workflow, preview, revision history, rollback, knowledge selection, and installation verification remain deferred.

## Widget Administration TASK-067B4

Widget administration now includes saved-draft knowledge selection, grant-bound draft preview, publish validation and confirmation, immutable revision history, rollback, passive embed installation evidence, and the TASK-067B5 controlled-pilot admin release gate.

## Widget Administration Controlled-Pilot Gate

TASK-067B5 adds the widget administration release gate for controlled pilot readiness:

```bash
npm run widget:admin:release:verify
```

The gate runs focused admin API hardening tests, admin frontend workflow tests, web lint/build, public widget pilot verification, pilot readiness, and writes `artifacts/widget-admin-readiness/report.json`. It does not deploy production infrastructure and does not declare GA readiness.

## Azure Controlled Pilot Infrastructure

TASK-068B1 adds the Azure infrastructure-as-code foundation for staging and controlled-production-pilot environments. It uses Bicep under `infrastructure/azure/` and provides local validation plus a non-destructive what-if wrapper:

```bash
npm run infra:azure:validate
npm run infra:azure:whatif -- staging
```

The foundation defines Azure Container Apps, Azure Container Registry, PostgreSQL Flexible Server, Blob Storage, Key Vault, Front Door, optional Redis, monitoring foundation, and a migration job. It does not deploy infrastructure, change DNS, or add production secrets.

## Azure CI/CD Foundation

TASK-068B2 adds manual Azure staging, production-pilot promotion, rollback, and validation workflows. These workflows use GitHub OIDC and protected environments; they do not deploy production automatically or enable customer pilot widgets.

See `docs/04_Engineering/Azure_CICD_Release_Promotion_and_Rollback.md` and `docs/06_Operations/Azure_Application_Deployment_Runbook.md`.
