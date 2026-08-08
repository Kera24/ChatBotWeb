# AI Trace Data and Privacy Policy

Status: implemented

## What is captured

Five tables (`ai_traces`, `ai_trace_stages`, `ai_retrieval_traces`, `ai_model_call_traces`, `ai_guardrail_traces` - see `AI_Observability_Architecture.md`) capture, by default, **metadata only**: status codes, latencies, token counts, cost figures, guardrail verdicts, reason codes, chunk IDs, similarity scores. No prompt text, retrieved document content, or generated answer text is stored unless the deployment explicitly opts into a higher-content retention mode (below).

## Retention (content) modes

Set via `AI_TRACE_CONTENT_MODE`, applied by `app.observability.redaction.apply_retention_policy`, and snapshotted onto each `ai_traces.content_mode` row at write time (so a later config change never retroactively reinterprets old rows):

| Mode | Behaviour |
|---|---|
| `metadata_only` (default) | No content preview fields are ever populated. |
| `redacted_preview` | Retrieved-chunk previews, prompt previews, and response previews are redacted (see below) and truncated to 500 characters before being stored. |
| `encrypted_full_content` | **Not implemented.** Falls back to `redacted_preview` behaviour and logs a one-time warning. Requires a KMS/key-management decision before real encryption-at-rest for full content can be built. |

## Redaction

`app.observability.redaction.redact_free_text` runs on every content preview before it is written, in this order:

1. **Structural secrets** - Stripe secret keys (`sk_live_...`), Stripe webhook secrets (`whsec_...`), AWS access keys (`AKIA...`), JWTs, generic `Bearer` tokens, database connection strings (`postgres://user:pass@host/db`), and this codebase's own public widget keys (`wpk_...`, pseudonymised, not deleted) and session tokens (`pss_...`), reusing the existing patterns in `app.operations.logging` rather than duplicating them.
2. **Custom tenant patterns** - optionally supplied via `AI_TRACE_CUSTOM_REDACTION_PATTERNS` (a JSON array of `{"name": ..., "pattern": ...}` objects), for deployment-specific identifiers (e.g. an internal case-ID format).
3. **Generic PII** - email addresses, phone numbers.

Structural secrets are matched before generic PII so a token embedded inside an email-shaped string is not half-redacted.

This is a **new, purpose-built module** for RAG prompt/response content - it is not a replacement for `app.operations.logging.redact()`, which remains the correct tool for structured operational-log redaction (a narrower, key-name-driven surface already used by `safe_attributes()`/OTel spans and the public-widget JSON logger). `redact_free_text` is only ever called from `SqlAlchemyAITraceRecorder` when populating `content_preview`/`raw_prompt_preview`/`raw_response_preview` - nowhere else in the request path.

## What is never captured, in any mode

- Passwords, API keys, session tokens, connection strings - redacted even in `redacted_preview` mode, never in `metadata_only`.
- Full document content - only a bounded preview (max 500 chars) of a *selected* chunk, only in `redacted_preview` mode.
- Anything from `app.operations.logging.SENSITIVE_FIELD_NAMES` if it ever flows through a structured-log path alongside a trace event.

## Access control

Trace metadata (status, latency, tokens, cost, guardrail verdicts) is readable by `org_owner`, `client_admin`, and `viewer` roles within the trace's own organisation (see `AI_Observability_Architecture.md`'s RBAC section). Content previews (`?include_content=true` on the trace-detail endpoint) additionally require `org_owner` or `client_admin` - viewers never see redacted content previews by default, only structural/quality signals. No role can ever read a trace belonging to a different organisation; cross-tenant lookups return 404.

## Retention window and cleanup

`AI_TRACE_RETENTION_DAYS` (default 90) controls how long trace rows are kept. `app.observability.retention.cleanup_expired_traces` deletes rows older than the cutoff, child tables first (`ai_trace_stages`, `ai_retrieval_traces`, `ai_model_call_traces`, `ai_guardrail_traces`), then `ai_traces`, batched (default 500 rows/iteration) to avoid long-held locks on a production database. Run via `python -m app.operations.observability_retention_cleanup` (see `AI_Trace_Retention_and_Redaction_Guide.md` for the operational runbook).

## Trade-offs, stated plainly

- Defaulting to `metadata_only` means a support engineer investigating "why did this answer look wrong" cannot see the actual retrieved text or generated answer without an operator explicitly enabling `redacted_preview` (or reading the corresponding `ChatMessage`/`Citation` rows directly, which already exist independently of this feature and follow their own, longer-standing access rules).
- `redacted_preview`'s regex-based redaction is a best-effort control, not a guarantee against every conceivable secret shape. It is verified against a fixed set of known secret formats (see `apps/api/tests/test_ai_redaction.py`) and an end-to-end no-leakage test (`test_ai_trace_no_secret_leakage.py`), not formally proven.
- `encrypted_full_content` is explicitly not built. Do not set `AI_TRACE_CONTENT_MODE=encrypted_full_content` expecting real encryption - it silently behaves as `redacted_preview`.
