# AI Observability Architecture

Status: implemented, live-verified locally (see Validation)

## Purpose

Every AI-serving request (dashboard test, public widget message, or evaluation case) is explainable end-to-end: request accepted → auth/tenant resolution → input policy → query embedding → retrieval → evidence sufficiency → prompt construction → provider call → structured output parsing → grounding verification → citation validation → output sanitisation → persistence → response completed. This document describes how that trace is generated, recorded, and served, and where its boundaries are.

## Correlation model

`app.observability.context.AITraceContext` carries `trace_id`, `request_id`, `conversation_id`, `eval_run_id`, `eval_case_id` through one RAG request. It is generated server-side and threaded explicitly as a field on `RAGOrchestrationRequest` - not via `contextvars`, because `app.evaluation.engine` runs `RAGOrchestrator.answer()` on a `ThreadPoolExecutor` worker thread while the caller's own session lives on another thread, and Python contextvars do not propagate into pool threads automatically. Explicit threading is the only mechanism guaranteed to tag every call site correctly, including evaluation-triggered ones.

- Authenticated path: `request_context_middleware` (`apps/api/app/main.py`) mints a `trace_id` per HTTP request (echoed via the `X-Trace-ID` response header) alongside the existing `request_id`/`X-Request-ID`. `apps/api/app/api/v1/workspaces.py`'s `/rag/answer` route reads both off `request.state` and passes them into the orchestrator.
- Public widget path: reuses the `trace_id` already generated in `app.access.tenant_resolution.service` (`NormalisedAccessContext.trace_id`) - one widget request has exactly one trace_id, not two.
- Evaluation path: `app.evaluation.engine._run_single_case` mints a fresh `trace_id` per case and tags it with `eval_run_id`/`eval_case_id`.
- `trace_id` is never included in the public widget's client-facing `public_response` payload (only in internal metadata / authenticated dashboard responses) - the public path already returns `request_id` for client-side correlation, which does not identify tenants.

## Data model

Five tables, added in migration `0017_ai_observability` (`apps/api/app/db/models/ai_trace.py`):

- **`ai_traces`** - one row per request. Root correlation row: `trace_id`, org/workspace/assistant/conversation IDs, channel, status, answer_state, fallback_used, total_latency_ms, denormalised provider/model/token/cost summary, `content_mode` (retention mode snapshot at write time), `eval_run_id`/`eval_case_id`, `otel_trace_id`/`otel_span_id` (a join key into whatever OTel backend is active, read defensively from the ambient OTel span - never the source of truth for our own IDs).
- **`ai_trace_stages`** - one row per pipeline stage (the 14 stages above), with status/latency/reason_code/safe_counts_json.
- **`ai_retrieval_traces`** - one row per chunk selected into the context window (rank, similarity_score, source_title, redacted content_preview). Chunks considered but not selected are not currently captured - see Limitations.
- **`ai_model_call_traces`** - one row per provider generation call: tokens, cost (nullable when pricing is unknown - never silently zero), `cost_calc_version`, `pricing_known`, latency, finish_reason, outcome, redacted prompt/response previews.
- **`ai_guardrail_traces`** - one row per guardrail layer evaluated (A-H, matching the layer comments in `app.ai.rag_orchestrator.RAGOrchestrator.answer`), verdict, blocked, reason_code.

All five tables carry denormalised `organisation_id`/`workspace_id` (matches the rest of this codebase's convention) and an indexed `created_at` for retention cleanup.

## Recording layer

`app.observability.ai_trace_recorder.AITraceRecorder` is a protocol with two implementations:

- `NoOpAITraceRecorder` - every method is a no-op. `RAGOrchestratorDependencies.trace_recorder` defaults to this, so every pre-existing call site that does not construct a real recorder keeps working unchanged.
- `SqlAlchemyAITraceRecorder` - writes through its **own** short-lived session (`session_factory`), never the orchestrator's request-scoped `db` session, so a trace-write failure can never roll back or interfere with conversation persistence, and vice versa. Every public method wraps its body in `try/except Exception: logger.debug(...)` - AI observability must never be able to break the primary request path. Stage/retrieval/guardrail/model-call rows are buffered in memory and flushed in one commit from `finish_trace()`; `start_trace()` writes and commits immediately so a trace row exists even if the request crashes before `finish_trace()` runs.

`app.observability.dependencies.build_ai_trace_recorder(db)` builds a recorder bound to the same engine as the caller's `db` session (via `db.get_bind()`) - correct for the single-threaded HTTP paths. `app.evaluation.engine._build_evaluation_trace_recorder` additionally checks the dialect and returns a no-op recorder on SQLite specifically (see Limitations) while using a real recorder on Postgres.

## Wiring into `RAGOrchestrator`

Every insertion point in `apps/api/app/ai/rag_orchestrator.py` is a single additive line placed immediately after an existing decision point - it never changes control flow, never changes a returned `answer_state`/`fallback_used`/guardrail decision, and uses values already computed locally. `RAGOrchestrationRequest`/`RAGOrchestrationResult`/`RAGOrchestratorDependencies` each gained one trailing optional field (`trace_context`, `trace_id`, `trace_recorder`), so no existing caller needed to change.

## Cost accounting

`AIModelCallTrace.pricing_known` is `False` and cost fields are `NULL` (never `0`) when the model's `ModelConfig.input_cost_per_million_tokens`/`output_cost_per_million_tokens` are unset. `ModelConfig.cost_calc_version` (default `"v1"`) is bumped manually whenever pricing changes, giving each cost row a versioned snapshot without a separate pricing-config subsystem. Aggregate metrics (by org/workspace/assistant/provider/model/day) are computed on read via SQL `GROUP BY` (see `app.observability.metrics`), not a materialised rollup table - acceptable at the controlled-pilot scale this platform currently targets (see ADR `0018-controlled-pilot-production-hosting-and-observability-model`).

## OpenTelemetry

See `docs/04_Engineering/OpenTelemetry_Setup_Guide.md` for the dual-path design (Azure Monitor vs. generic OTLP, mutually exclusive, Azure wins if both are configured).

## API and UI

See the AI Metrics Dictionary and Retrieval Debugger Guide for what the `/observability` dashboard and `/observability/traces/{traceId}` detail page show, and the RBAC section below for who can see it.

## RBAC and tenant isolation

`GET .../observability/traces`, `.../traces/{trace_id}`, `.../metrics`, `.../anomalies` require `{org_owner, client_admin, viewer}` membership (matching `conversations.py`'s tier). `.../alerts` and the `?include_content=true` query param on trace detail require `{org_owner, client_admin}` (matching `audit_events.py`'s stricter tier). Every trace lookup verifies the fetched row's `organisation_id`/`workspace_id` match the caller's tenant context and returns 404 (not 403) on mismatch, exactly like `conversations.py`'s `_ensure_workspace`/`get_workspace_conversation_detail` pattern - a client can never learn whether a trace_id exists in another tenant.

## Explicitly deferred / lightweight this pass

- **`encrypted_full_content` retention mode** - schema/enum exist; falls back to `redacted_preview` with a one-time logged warning. Needs a KMS/key-management decision out of scope for this pass.
- **Rejected-chunk capture** - `app.services.retrieval_context.assemble_retrieval_context` does not currently return candidates that were considered but not selected into the context window, so `ai_retrieval_traces` only records selected chunks. Extending `RetrievalContextResult` to carry the full candidate list is a natural follow-up.
- **Grounding verification** - `app.ai.guardrails.grounding.verify_grounding` is not wired into the live pipeline; its trace stage is recorded as `status="skipped", reason_code="not_wired_into_pipeline"` rather than fabricating a pass/fail it never ran. Evidence sufficiency is the functional guardrail that currently covers this concern.
- **Materialised cost/metrics rollups** - on-read aggregation only; flagged as a scale follow-up.
- **AI trace recording on SQLite for evaluation runs** - see Limitations below.

## Limitations

**SQLite dev/test tier: evaluation-triggered AI traces are not recorded.** `app.evaluation.engine` runs `RAGOrchestrator.answer()` on a `ThreadPoolExecutor` worker thread while the evaluation run's own long-lived session is alive on the main thread. During development of this feature, this reproduced as spurious "database is locked" errors that could surface on the evaluation engine's own write path (not just the trace recorder's), which is unacceptable given the "never breaks the primary feature" requirement. `app.evaluation.engine._build_evaluation_trace_recorder` therefore returns a no-op recorder whenever the underlying dialect is `sqlite`, and a real recorder otherwise. Production evaluation runs against Postgres (proper MVCC, no single-writer file lock) are fully traced and tagged with `eval_run_id`/`eval_case_id`. Authenticated-dashboard and public-widget traces are unaffected on any dialect, including SQLite - only the evaluation engine's specific cross-thread pattern requires this guard.

## Validation

Run `npm run api:test`, `npm run web:test`, `npm run web:lint`, `npm run web:build`. Manual verification performed for this feature: registered a tenant, created an assistant, seeded a pre-embedded knowledge chunk, asked a real grounded question through `/rag/answer`, and confirmed - via both the raw API responses and a live browser session - that the resulting trace appears correctly in `/observability` (dashboard metrics, recent traces list, deterministic trend signal) and `/observability/traces/{traceId}` (full 14-stage timeline, retrieval debugger, guardrail outcomes for all five layers, model call and cost breakdown).
