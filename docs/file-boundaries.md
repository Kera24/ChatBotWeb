# File Boundaries by Feature

Maps each major feature to its primary/secondary/test files, and what should not be touched when working on it. Use this before starting any feature-scoped task to avoid drifting into unrelated files. See `docs/architecture/*.md` for the "why," this doc is the "where."

## Analytics

- **Primary**: `apps/web/app/analytics/page.tsx`, `apps/web/lib/api/analytics.ts`, `apps/web/components/analytics/*`.
- **Secondary**: reads from Conversations, Documents, Widgets, and Review APIs (composes them, doesn't own their data).
- **Tests**: co-located `apps/web/components/analytics/*.test.tsx`.
- **Do not modify**: the underlying Conversations/Documents/Widgets/Review APIs as part of an Analytics-only task.

## Knowledge (documents)

- **Primary**: `apps/api/app/api/v1/documents.py`, `apps/api/app/services/{document_lifecycle,chunking,embeddings,manual_extraction}.py`, `apps/api/app/db/models/{document,document_version,chunk}.py`, `apps/web/app/knowledge/page.tsx`, `apps/web/components/knowledge/*`.
- **Secondary**: `apps/api/app/services/vector_search.py` (consumes chunks, doesn't own ingestion).
- **Tests**: `apps/api/tests/test_document*.py`, `test_chunking*.py`, `test_embedding*.py`.
- **Do not modify**: `app.services.document_lifecycle`'s transition map without understanding every current caller — this is the single enforcement point for valid status transitions.

## Widget (assistant configuration)

- **Primary**: `apps/api/app/access/widget_admin/*`, `apps/api/app/db/models/public_access.py` (Widget, WidgetConfigurationRevision, etc.), `apps/web/app/widgets/*`.
- **Secondary**: `apps/api/app/access/credentials/*` (origins, public credentials).
- **Tests**: `apps/api/tests/test_widget_admin_*.py`.
- **Do not modify**: the draft/publish revision-cloning logic without understanding the immutable-published-revision invariant.

## Chat / Chatbot playground

- **Primary**: `apps/web/app/chatbot/*`, `apps/api/app/api/v1/ai.py` (direct model-test path), `apps/api/app/api/v1/workspaces.py` (`/rag/answer`, the real dashboard-test path).
- **Secondary**: `app.ai.rag_orchestrator` (see `retrieval` skill for the pipeline itself).
- **Do not modify**: `app.ai.service.AICoreService` unless the task is specifically about the provider-call layer.

## Review (Knowledge Gaps)

- **Primary**: `apps/api/app/api/v1/review.py`, `apps/api/app/repositories/review_repository.py`, `apps/web/app/review/unanswered/*`.
- **Tests**: `apps/api/tests/test_review*.py`.
- **Do not modify**: `REVIEW_ANSWER_STATES`/`REVIEW_STATUSES` enums without checking every consumer (dashboard filters, analytics).

## Users

- **Primary**: `apps/api/app/api/v1/memberships.py`, `apps/api/app/repositories/membership_repository.py`, `apps/web/app/users/*`, `apps/web/components/users/*`.
- **Do not modify**: `VALID_ORGANISATION_ROLES` without understanding every RBAC dependency call site across the whole API — this is a cross-cutting enum.

## Settings

- **Primary**: `apps/api/app/api/v1/settings.py`, `apps/web/app/settings/*`, `apps/web/components/settings/*`.
- **Do not modify**: `EDITABLE_FIELDS` to add a new editable field without confirming it shouldn't instead be `ENVIRONMENT_CONTROLLED_FIELDS` or `SECRET_MANAGED_FIELDS` — this distinction is deliberate.

## Billing

See `.skills/billing/SKILL.md` and `docs/architecture/billing.md` for the full boundary — summarized: `apps/api/app/billing/*`, `apps/api/app/api/v1/billing*.py`, `apps/web/app/billing/*`. **Requires explicit instruction to modify pricing/limits/webhook logic.**

## Authentication

- **Primary**: `apps/api/app/auth/*`, `apps/api/app/api/v1/auth.py`, `apps/web/lib/auth/*`, `apps/web/app/{login,register,forgot-password,reset-password,onboarding}/*`.
- **Do not modify**: `require_organisation_role`/`get_development_current_user`'s core resolution logic in `apps/api/app/api/deps.py` without understanding every router that depends on it (nearly all of them).

## Landing / Pricing (marketing)

- **Primary**: `apps/web/app/page.tsx`, `apps/web/components/landing/*`, `apps/web/app/pricing/page.tsx`, `apps/web/components/pricing/*`.
- **Do not modify**: `PLAN_CATALOG` pricing here — the marketing pricing display should read from or match the same source of truth as `apps/api/app/billing/plans.py`, not hardcode a divergent number.

## Dashboard (shell/navigation)

- **Primary**: `apps/web/components/dashboard-shell.tsx`, `apps/web/lib/navigation.ts`.
- **Do not modify**: the overall shell structure/layout for a single-feature task — only add the one nav entry + icon mapping for a new top-level page.

## Evaluation

See `.skills/evaluation/SKILL.md` and `docs/architecture/evaluation.md`. Primary: `apps/api/app/evaluation/*`, `apps/web/app/evaluation/*`. **`policy.py`/`gate.py` require explicit instruction to change.**

## Continuous Evaluation (Production Feedback Loop)

See `docs/04_Engineering/Evaluation_Production_Feedback_Loop.md`, `docs/04_Engineering/Candidate_Triage_Guide.md`, `docs/04_Engineering/Dataset_Promotion_Policy.md`. Primary: `apps/api/app/evaluation/feedback/*`, `apps/api/app/evaluation/production_gate.py`, `apps/api/app/evaluation/feedback_metrics.py`, `apps/api/app/repositories/evaluation_candidate_repository.py`, `apps/api/app/api/v1/evaluation_candidates.py`, `apps/api/app/db/models/evaluation_candidate.py`, `apps/api/app/operations/{production_signal_scan,eval_focused_run,eval_regression_report,eval_release_gate_check}.py`, `apps/web/app/feedback-loop/*`, `apps/web/components/feedback-loop/*`, `apps/web/lib/api/feedback-loop.ts`. **Promotion requires an explicit human `accepted` triage decision — never add an automatic-promotion path.** Only ever writes to the `evaluation_cases` DB table, never to `apps/api/app/evaluation/fixtures/*.json`.

## Prompt Management

See `docs/architecture/prompts.md`, `docs/03_AI/Prompt_Layering_and_Security_Policy.md`, `docs/04_Engineering/Prompt_Versioning_Guide.md`, `docs/04_Engineering/Prompt_Evaluation_and_Promotion_Policy.md`, `docs/04_Engineering/Prompt_Experiment_Guide.md`, `docs/06_Operations/Prompt_Rollback_Runbook.md`. Primary: `apps/api/app/prompts/*`, `apps/api/app/db/models/prompt.py`, `apps/api/app/repositories/prompt_repository.py`, `apps/api/app/api/v1/prompts.py`, `apps/api/app/schemas/prompt_management.py`, `apps/api/app/evaluation/prompt_promotion_gate.py`, `apps/api/app/operations/prompt_promote.py`, `apps/web/app/prompts/*`, `apps/web/components/prompts/*`, `apps/web/lib/api/prompts.ts`. **Never expose full platform-immutable (`platform_core`) content to a non-super-admin caller — `safe_template_summary()`/`safe_version_summary()` are the single enforcement point for this redaction, don't bypass them.** The code-defined default prompt in `app.ai.prompt_registry` and the preview-only `POST /{workspace_id}/retrieval/prompt` endpoint (`app.services.prompt_assembly`) are deliberately left untouched by this feature - see `docs/architecture/prompts.md`'s "Known, pre-existing drift" section before considering unifying them.

## Guardrails

See `.skills/guardrails/SKILL.md` and `docs/architecture/guardrails.md`. Primary: `apps/api/app/ai/guardrails/*` + wiring in `apps/api/app/ai/rag_orchestrator.py`.

## Observability

See `.skills/observability/SKILL.md` and `docs/03_AI/AI_Observability_Architecture.md`. Primary: `apps/api/app/observability/*`, `apps/web/app/observability/*`.

## Deployment / Infrastructure

See `.skills/deployment/SKILL.md` and `docs/architecture/deployment.md`. **`docker-compose.prod.yml`, `deployment/caddy/Caddyfile`, `deployment/backup/*.sh`, `infrastructure/azure/**`, and `.github/workflows/*` all require explicit instruction to modify.**

## Cutting across every feature (touch only with a clear reason)

- `apps/api/app/api/deps.py` — RBAC/current-user resolution.
- `apps/api/app/core/config.py` — settings.
- `apps/api/app/db/session.py` — DB session/engine.
- `apps/web/lib/api/client.ts` — the shared API request function.
- `apps/web/lib/auth/session.ts` — the shared session gate.
- `apps/web/app/globals.css` — the shared stylesheet.
