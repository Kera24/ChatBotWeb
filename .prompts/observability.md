# Prompt Template: AI Observability

Use this when the task touches AI request tracing, redaction, retention, alerts, drift signals, or the `/observability` dashboard.

## Scope

`apps/api/app/observability/*`, `apps/api/app/db/models/ai_trace.py`, `apps/api/app/api/v1/observability.py`, `apps/web/app/observability/*`, `apps/web/components/observability/*`. Full reference: `docs/03_AI/AI_Observability_Architecture.md` (read this in full before starting — it documents several non-obvious pitfalls already discovered, don't rediscover them).

## Constraints

- The trace recorder must be fail-safe: it can never be allowed to break the request it's observing. Every recorder method wraps its body in try/except; the default dependency is a no-op.
- Trace context uses explicit parameter threading (`AITraceContext`), not `contextvars` — the evaluation engine's `ThreadPoolExecutor` doesn't propagate them. See `docs/architecture/evaluation.md`.
- Content redaction (`app.observability.redaction`) is the only path allowed to write prompt/response previews into trace tables, and only when `AI_TRACE_CONTENT_MODE != metadata_only`.
- Never label an automated metric "hallucination rate" — see `docs/03_AI/AI_Metrics_Dictionary.md`.
- SQLite + evaluation runs: AI trace recording is intentionally disabled there (real cross-thread contention, documented in the Architecture doc's Limitations) — don't "fix" this by re-enabling it without re-reading why it was disabled.

## Validation

`npm run api:test` (the observability test files are `test_ai_trace_*.py`, `test_observability_api.py`, `test_otel_generic_export.py`, `test_public_authenticated_trace_parity.py`). If frontend changed, also `npm run web:test && npm run web:lint && npm run web:build`.

## Reporting

Short Report by default; Full Report if the data model, redaction rules, or retention behavior changed (privacy-relevant).

## Expected output

New/modified files under `app/observability/`, matching test coverage, and — if content redaction rules changed — a rerun of `test_ai_trace_no_secret_leakage.py` explicitly called out in the report.

## What NOT to modify

- The fail-safe wrapping on `SqlAlchemyAITraceRecorder` (removing it reintroduces the risk of trace-recording breaking the primary request).
- `AI_TRACE_CONTENT_MODE` default (`metadata_only`).
- `docker-compose.prod.yml` (the observability stack is a separate, additive compose file — `docker-compose.observability.yml`).
