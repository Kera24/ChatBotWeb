# Overall System Architecture

Current state only. For philosophy behind these choices, see `docs/CONSTITUTION.md` and `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`. For roadmap, see `future-roadmap.md` in this directory.

**Supersedes `docs/02_Architecture/01_System_Architecture.md` as the accurate current-state reference.** That earlier document (Version 0.1, Status: Draft) describes an early target architecture (e.g. a Redis-queue-based ingestion/embedding service) that predates and differs from what was actually built (ingestion runs synchronously within the API today — see `knowledge-ingestion.md`). Keep the older document for historical intent; treat this `docs/architecture/` tree as the source of truth for what the code actually does right now.

## Monorepo layout

```
apps/api             FastAPI backend (Python)
apps/web              Next.js dashboard (App Router)
apps/widget           Embeddable widget iframe app
packages/widget-sdk    Widget loader SDK (published as @yoranix/widget-sdk)
deployment/            Caddy, backup/restore scripts, VPS observability stack
infrastructure/azure/  Bicep IaC, kept live for a future Azure migration (not the active deploy target)
docs/                  All documentation - see docs/README.md and docs/file-boundaries.md
tests/widget-browser/  Playwright e2e suite for the widget
```

## Request flow (authenticated dashboard)

Browser → Next.js server component (`apps/web/app/<route>/page.tsx`) → `requireDashboardSession()` (reads/validates the `yoranix_session` cookie against `GET /api/v1/auth/me`) → typed loader in `apps/web/lib/api/<feature>.ts` → FastAPI route in `apps/api/app/api/v1/<feature>.py` → RBAC dependency (`require_organisation_role`) → repository function → Postgres/SQLite.

## Request flow (public widget)

Browser (customer's site) → widget iframe (`apps/widget`) → `POST /api/v1/widget/{public_key}/messages` → `app.access.gateway.PublicAccessGateway` (origin validation, rate limiting, idempotency, cost controls — see `app.access.*`) → `app.access.messages.rag_adapter.PublicWidgetRAGAdapter` → the same `RAGOrchestrator` used by the authenticated path → sanitized public response (never includes internal IDs like `trace_id`, `organisation_id`).

## The three tenant layers

Organisation → Workspace → Assistant (Widget). Every tenant-scoped table carries `organisation_id` and `workspace_id`; assistant-scoped tables also carry `widget_id`/`assistant_id`. See `docs/architecture/authentication.md` for how this is enforced at the API layer.

## Core subsystems (one doc each in this directory)

| Subsystem | Doc |
|---|---|
| Frontend structure | `frontend.md` |
| Backend structure | `backend.md` |
| Auth, sessions, RBAC | `authentication.md` |
| Billing/Stripe | `billing.md` |
| RAG retrieval pipeline | `retrieval.md` |
| Conversation context (or lack thereof) | `memory.md` |
| Evaluation framework | `evaluation.md` |
| Guardrails | `guardrails.md` |
| AI observability | `observability.md` |
| Document upload/processing | `knowledge-ingestion.md` |
| Embeddings/pgvector | `vector-storage.md` |
| Deployment | `deployment.md` |
| Test conventions | `testing.md` |
| What's next | `future-roadmap.md` |

## Cross-cutting things every subsystem shares

- **RBAC**: `apps/api/app/api/deps.py`'s `require_organisation_role({...})`, roles `org_owner`/`client_admin`/`contributor`/`viewer` (+ cross-tenant `super_admin`).
- **Response envelope**: `apps/api/app/schemas/common.py::success_response(data, meta)` → `{"success": true, "data": ..., "meta": {...}}`.
- **Audit trail**: `apps/api/app/db/models/audit_event.py` / `app.repositories.audit_repository` — entity-lifecycle audit events (document status changes, membership changes, etc.). Distinct from AI observability traces (`observability.md`), which are request-level, not entity-lifecycle.
- **Config**: a single frozen dataclass `Settings` in `apps/api/app/core/config.py`, fields as `FIELD: type = getenv("ENV_VAR", "default")`.
- **Migrations**: Alembic, numbered `NNNN_description.py` in `apps/api/alembic/versions/`, dialect-guarded FK creation for SQLite/Postgres compatibility.

## Known architectural gaps (as of this writing)

- No live AI provider — only `MockAIProvider`. See `retrieval.md`.
- No multi-turn conversation memory. See `memory.md`.
- No component library or CSS framework on the frontend — plain CSS. See `docs/design/design-system.md`.
- Email delivery (verification, password reset) is not wired up — endpoints exist but respond that delivery isn't configured. See `authentication.md`.
