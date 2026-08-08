# CLAUDE.md — Conversa Developer Operating System

This file is the primary instruction source for Claude Code working in this repository. Read it before starting any task. It exists to make future prompts short: instead of re-explaining architecture and conventions every time, a prompt can say "Use the Frontend UI skill. Implement Task X." and this file plus `.skills/`/`.prompts/`/`docs/` supply the rest.

**Reading order for a new task**: this file → the relevant skill in `.skills/` → the relevant doc(s) in `docs/architecture/` → `docs/file-boundaries.md` for the feature in question → `docs/validation-policy.md` to decide what to run → `docs/reporting-policy.md` to decide how to report back.

## Project overview

Conversa is a multi-tenant SaaS platform where organisations create, train, test, publish, monitor, and improve AI knowledge-grounded assistants ("widgets"). Backend: FastAPI + SQLAlchemy + Postgres/pgvector (SQLite fallback for local dev/tests). Frontend: Next.js App Router, plain CSS (no Tailwind, no component library). Widget: a separately-built embeddable iframe app + loader SDK. See `docs/architecture/overall-system.md` for the full picture.

## Architecture summary

- **`apps/api`** — FastAPI backend. Routers in `app/api/v1/*`, business logic in `app/services/*` and feature-specific service modules (`app/auth/`, `app/billing/`, `app/access/`, `app/evaluation/`, `app/observability/`), AI/RAG pipeline in `app/ai/*`, ORM models in `app/db/models/*`, Alembic migrations in `alembic/versions/`.
- **`apps/web`** — Next.js dashboard. Server Components in `app/<route>/page.tsx` call `requireDashboardSession()` then a typed loader in `lib/api/*.ts`; presentational components live in `components/<feature>/`.
- **`apps/widget`** + **`packages/widget-sdk`** — the embeddable chat iframe app and its loader script, built and versioned independently.
- **`docs/architecture/*.md`** — one file per subsystem; read the relevant one before touching that subsystem.

## Core philosophy

- Reuse existing patterns exactly. Every feature area in this codebase already has an established shape (RBAC dependency, repository function style, test fixture, page/loader/component split). Copy the pattern; do not invent a new one.
- Additive over invasive. Prefer new files/new trailing-optional-fields over restructuring existing contracts, especially in `app.ai.rag_orchestrator` and anything with existing test coverage.
- Evidence over assumption. Read the actual file before claiming what it does. Run the actual test before claiming it passes.
- Small, correct, verified changes beat large, unverified ones.

## Coding standards

- Match the file's existing style exactly (import grouping, dataclass vs Pydantic model choice, naming). Do not introduce a new state-management library, CSS framework, or ORM pattern without being asked.
- No comments that restate what the code does. Comments only for non-obvious *why* (see the extensive precedent throughout `app/ai/guardrails/*` and `app/ai/rag_orchestrator.py`).
- Backend: type hints everywhere, `Session` passed explicitly (no ambient DB context), repository functions are plain functions taking `db: Session` first (not classes) — see `app/repositories/conversation_repository.py` as the reference shape.
- Frontend: Server Component page → typed `lib/api/*.ts` loader → dumb presentational component. No client-side data fetching for initial page load.

## Validation rules

See `docs/validation-policy.md` for the full decision table. Short version: run the narrowest test suite that covers your change while developing; before calling a task done, run the commands listed in `docs/validation-policy.md` for the area(s) you touched. Never claim a test suite passes without having run it in this session.

## Testing policy

- New backend logic gets a new or extended test file following the nearest existing convention (see `docs/architecture/testing.md`).
- New frontend components get a co-located `*.test.tsx` using Vitest + Testing Library, mocking the `lib/api/*` boundary — never making real network calls in a unit test.
- UI changes: after tests pass, actually run the dev server and look at the feature (see the `run` skill and `verify` skill) before reporting done. Type checks and test suites verify correctness, not that a human would recognize the feature as working.

## Git policy

- Never commit or push unless explicitly asked in that specific turn. Approval for one commit/push does not carry to future turns.
- Never use `--no-verify`, `--force` (without explicit instruction), or amend published commits.
- Before any destructive git operation, run `git status` first.

## Reporting format

See `docs/reporting-policy.md`. Default to the **Short Report** format (files changed, validation run, remaining limitations, git status). Only use the Full Report format when explicitly asked for a detailed report, or when the change is large/architecturally significant enough that a short report would hide something the user needs to know.

## Security rules

- Never weaken tenant isolation. Every tenant-scoped query filters by `organisation_id` **and** `workspace_id`; every tenant-scoped API route re-validates the fetched row's tenant IDs match the caller's context (404, not 403, on mismatch — don't leak existence).
- Never log or persist secrets, passwords, session tokens, API keys, or full prompt/response content without going through the existing redaction path (`app.operations.logging.redact` for structured logs, `app.observability.redaction` for AI trace content).
- Never introduce a new way to bypass RBAC (`require_organisation_role`, `require_super_admin`) — extend the existing dependency, don't route around it.
- Treat anything in `.env*`, `apps/api/app/core/config.py` secret-shaped fields, and Stripe/Azure credentials as material never to print, commit, or send anywhere.

## UI principles

See `docs/design/design-system.md` for the actual tokens/classes. In short: reuse existing CSS classes (`.card`, `.statePanel`, `.badge`, `.actionButton`) before writing new CSS; match the existing page-shell pattern (`DashboardShell` + `navigationItems`); don't introduce Tailwind, a component library, or a new theming mechanism — this app is plain CSS with CSS custom properties, OS-driven `prefers-color-scheme`, and no JS theme toggle today.

## Evaluation philosophy

Quality is measured, not assumed. The evaluation framework (`app/evaluation/*`, `docs/architecture/evaluation.md`) runs real assistant questions through the real `RAGOrchestrator` and scores retrieval + answer quality deterministically, with optional LLM-judge grading. **Never change evaluation pass/fail thresholds, scoring weights, or gate policy without explicit instruction** — these encode a deliberate, previously-agreed quality bar.

## Guardrail philosophy

Guardrails are layered (A through H, see `docs/architecture/guardrails.md`) and each layer has a narrow, single responsibility: input policy, evidence sufficiency, citation policy, document sanitization, output safety. Never remove or weaken a guardrail layer to make a feature "work." If a guardrail is blocking something that should be allowed, fix the guardrail's logic explicitly and explain why, don't bypass it.

## Deployment philosophy

Initial production deployment is a **low-cost single-VPS Docker Compose** setup (`docker-compose.prod.yml`), not Azure — Azure infrastructure (`infrastructure/azure/`) is retained and kept compatible for a future migration but is not the active deployment target. Keep new infrastructure code Azure-migration-friendly (OpenTelemetry over vendor-specific telemetry, provider-neutral config) without requiring Azure. See `docs/architecture/deployment.md`.

## Known constraints

- Only a mock AI provider (`MockAIProvider`) and mock/Ollama embedding providers exist today — no live OpenAI/Anthropic/Azure OpenAI provider is wired in yet.
- No multi-turn conversation memory — every question is answered independently of prior turns in the same conversation (see `docs/architecture/memory.md`).
- SQLite (used for local dev/tests) has no real vector column — pgvector only exists on Postgres; SQLite computes cosine similarity in Python at query time.
- The design system's `.dark` CSS rules exist but are currently dormant — no code path toggles a dark-mode class; dark-mode behavior today is entirely `prefers-color-scheme`-driven with an override layer that forces most surfaces light for readability.

## Things Claude must NEVER do

- Change evaluation thresholds, scoring weights, or gate policy without explicit instruction.
- Weaken or bypass a guardrail layer, RBAC check, or tenant-isolation filter.
- Modify billing/Stripe logic, pricing, or webhook handling without explicit instruction.
- Modify database schema or write a migration without being asked to.
- Commit, push, or run destructive git operations without being asked in that turn.
- Introduce a new frontend framework, CSS methodology, state library, or ORM pattern unprompted.
- Claim a test passed, a build succeeded, or a UI feature works without having actually run it in this session.
- Store raw secrets, full prompts, or full AI responses in logs or trace tables outside the existing redaction/retention controls.

## Things Claude should ALWAYS do

- Read the relevant `docs/architecture/*.md` and `.skills/*/SKILL.md` before starting.
- Check `docs/file-boundaries.md` for the feature area before touching files.
- Match existing patterns (RBAC dependency shape, repository function shape, test fixture shape, page/loader/component split) exactly.
- Run the validation commands from `docs/validation-policy.md` appropriate to what changed.
- Report using the format in `docs/reporting-policy.md`, defaulting to Short Report.
- Flag any place a change might touch tenant isolation, guardrails, evaluation thresholds, or billing, even if not asked.

## Default validation commands

| Area touched | Minimum commands |
|---|---|
| `apps/api/app/**` (non-migration) | `npm run api:test` |
| `apps/api/alembic/**` | `npm run api:test` (in-memory SQLite tests use `Base.metadata.create_all`, migrations are validated separately — see `docs/validation-policy.md`) |
| `apps/web/**` | `npm run web:lint && npm run web:build && npm run web:test` |
| `apps/api/app/evaluation/**` | `npm run eval:test` in addition to `api:test` |
| `apps/widget/**` or `packages/widget-sdk/**` | `npm run widget-sdk:test && npm run widget:test`; add Playwright (`npm run widget:e2e:chromium`) only if behavior visible to the embed changed |
| Cross-cutting / pre-handoff | `npm run verify` (full chain, slow — see `docs/validation-policy.md` for when this is actually required) |

Always also run `git diff --check` before finishing if any files were touched.

## How to decide when full verification is required

Full `npm run verify` (which includes widget Playwright e2e and takes several minutes) is **not** required for every change. See `docs/validation-policy.md`'s decision table. Rule of thumb: run it only when the change is cross-cutting (touches shared config, CI, or multiple apps/packages simultaneously) or right before reporting a large multi-area task as complete.

## How to preserve existing behaviour

- Before changing a function/endpoint/component, grep for all its call sites and check existing tests covering it.
- Prefer adding a new optional trailing field/parameter over changing an existing signature.
- When wiring a new cross-cutting concern (like a recorder, a middleware, a new dependency) into an existing hot path, make it fail-safe by default (wrap in try/except, default to a no-op) so it cannot break the feature it's attached to — see `app.observability.ai_trace_recorder` for the reference pattern.
- Re-run the existing test suite for anything you touch before and conceptually compare — a passing suite after your change with the same test count (or more) is the bar.

## Rules for frontend work

See `.skills/frontend-ui/SKILL.md` and `docs/design/design-system.md`. Server Component page (`app/<route>/page.tsx`) → `requireDashboardSession()` → typed loader in `lib/api/<feature>.ts` → dumb component in `components/<feature>/`. Reuse `DashboardApiError`/`isDashboardApiError`/`messageForApiError` for error handling, `AccessDeniedState`/`ErrorState` for failure UI. Add exactly one nav entry (`lib/navigation.ts` + `dashboard-shell.tsx`'s `navIcons`) for a new top-level page — never restructure the nav for a feature task.

## Rules for backend work

See `.skills/backend-api/SKILL.md`. New endpoints go in the relevant `app/api/v1/<feature>.py` router, registered in `app/api/v1/router.py`'s `API_V1_ROUTER_REGISTRATIONS`. RBAC via `require_organisation_role({...})` matching the nearest precedent (`conversations.py` for viewer-inclusive, `audit_events.py` for owner/admin-only). Repository functions in `app/repositories/<feature>_repository.py`, plain functions not classes.

## Rules for AI work

See `docs/architecture/retrieval.md`, `docs/architecture/guardrails.md`, `docs/architecture/evaluation.md`. Never bypass the guardrail chain in `RAGOrchestrator.answer()`. Never call a production-quality metric "hallucination rate" — use the vocabulary in `docs/03_AI/AI_Metrics_Dictionary.md` (unsupported-answer signal / grounding failure / evidence-insufficient response / review-confirmed incorrect answer).

## Rules for documentation

Update the relevant `docs/architecture/*.md` file when you change something it describes — documentation drift is a real cost for future prompts. Do not create new top-level docs directories; add to the existing structure (`docs/architecture/`, `docs/03_AI/`, `docs/04_Engineering/`, `docs/06_Operations/`, etc. — see `docs/file-boundaries.md`).

## Rules for migrations

Follow the numbered-filename convention (`NNNN_description.py`, revision id == filename stem), chain `down_revision` to the current head, follow the SQLite/Postgres dialect-guard pattern in the most recent existing migration for FK creation. Never edit a migration that has already been referenced by another migration's `down_revision` — add a new one instead.

## Rules for production safety

Never modify `docker-compose.prod.yml`, `deployment/caddy/Caddyfile`, backup/restore scripts, or Azure infrastructure definitions (`infrastructure/azure/`) without explicit instruction — these are production-safety-critical and changes here are hard to reverse quickly.
