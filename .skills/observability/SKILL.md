# Skill: AI Observability

## Purpose

Work on AI request tracing, redaction, retention, alerts/drift signals, the OTel integration, the VPS observability stack, or the `/observability` dashboard.

## When to use

Any task touching `apps/api/app/observability/*`, the `ai_traces`/`ai_trace_stages`/`ai_retrieval_traces`/`ai_model_call_traces`/`ai_guardrail_traces` tables, `apps/api/app/api/v1/observability.py`, or `apps/web/app/observability/*`. **Read `docs/03_AI/AI_Observability_Architecture.md` in full first** — it documents the reasoning and several already-discovered pitfalls (don't rediscover them at cost).

## Architecture assumptions

- Trace context uses explicit parameter threading (`AITraceContext`), never `contextvars` (the evaluation engine's thread pool breaks that).
- The recorder is fail-safe by construction — every write wraps in try/except, defaults to a no-op, uses its own DB session never the request's.
- Content redaction defaults to `metadata_only` (nothing stored); `redacted_preview` redacts+truncates; `encrypted_full_content` is not implemented (falls back safely).
- AI trace recording is intentionally a no-op for evaluation runs on SQLite specifically (real cross-thread contention, documented, not a bug).

## Files typically modified

- `apps/api/app/observability/*.py` (recorder, redaction, metrics, drift, alerts, retention, dependencies, context).
- `apps/api/app/db/models/ai_trace.py` + a new Alembic migration if the schema changes.
- `apps/api/app/api/v1/observability.py`, `apps/api/app/repositories/observability_repository.py`, `apps/api/app/schemas/observability.py`.
- `apps/web/app/observability/*`, `apps/web/components/observability/*`, `apps/web/lib/api/observability.ts`.
- `apps/api/tests/test_ai_trace_*.py`, `test_observability_api.py`, `test_otel_generic_export.py`, `test_public_authenticated_trace_parity.py`.

## Files never modified

- The fail-safe try/except wrapping in `SqlAlchemyAITraceRecorder` — removing it reintroduces risk to the primary request path.
- `docker-compose.prod.yml` — the observability stack is `docker-compose.observability.yml`, additive only.
- `AI_TRACE_CONTENT_MODE`'s default value.

## Validation commands

```
npm run api:test
npm run web:test
npm run web:lint
npm run web:build
```

## Expected report format

Short Report by default; Full Report if the data model, redaction rules, or retention behavior changed.

## Common pitfalls

- Assuming `db.get_bind()` session-sharing is safe across threads — it isn't for a cross-thread caller (this is exactly why the evaluation-engine SQLite guard exists).
- Reading `row.id` after a session commits and the `with` block has closed — SQLAlchemy expires attributes on commit; read IDs while still inside the session block.
- Forgetting the CORS `Access-Control-Allow-Origin` must exactly match the browser's actual origin (including port) when testing cross-port locally — a mismatch silently blocks the request with no server-side log entry.
- Storing raw prompt/response content without going through `apply_retention_policy`/`redact_free_text`.

## Best practices

- Add new trace-recording calls as single additive lines immediately after the value they need is already computed, exactly following the existing per-stage pattern in `rag_orchestrator.py`.
- When adding a new alert threshold or drift signal, follow the existing deterministic-threshold pattern in `app.observability.alerts`/`app.observability.drift` — no ML.
- Verify redaction changes with `apps/api/tests/test_ai_redaction.py` and `test_ai_trace_no_secret_leakage.py` specifically, not just the general suite.
