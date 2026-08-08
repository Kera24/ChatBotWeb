# Observability Checklist

## Required validation

- `npm run api:test` covering the observability test suite (trace recording, redaction, no-secret-leakage, retention, API/RBAC).

## Things to verify

- New instrumentation follows the fail-safe pattern: trace-recorder failure never breaks the request it's attached to (no-op default, try/except around every recorder write).
- New trace/prompt/response content goes through redaction (`app.observability.redaction`) before being persisted as a preview.
- New trace fields are additive to `ai_traces`/`ai_trace_stages`/`ai_retrieval_traces`/`ai_model_call_traces`/`ai_guardrail_traces` — no breaking schema change.
- RBAC on any new observability endpoint matches the existing viewer/content-role split (`ObservabilityViewerDependency`/`ObservabilityContentDependency`).
- No unredacted secret, password, token, or full prompt/response content is logged or persisted outside the existing redaction/retention path.

## Common mistakes

- Making the trace recorder a hard dependency (breaks the request on a trace-write failure).
- Logging raw prompt/response content bypassing redaction "just for debugging."
- Adding a new observability endpoint without the RBAC role split.

## Required documentation

- Update `docs/architecture/observability.md`/`docs/engineering/observability.md`/`docs/03_AI/AI_Observability_Architecture.md` for any trace-model change.

## Definition of Done

Fail-safe behavior verified by test (recorder failure doesn't break the request); redaction verified on every new content field; RBAC verified; no secret-leakage test failures.
