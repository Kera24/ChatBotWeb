# AI Trace Retention and Redaction Guide

Status: implemented

This is the operational companion to `AI_Trace_Data_and_Privacy_Policy.md` (which explains *what* is captured and *why*) - this guide covers *how to run and configure* retention and redaction in a live deployment.

## Configuring content retention

Set `AI_TRACE_CONTENT_MODE` in the API's environment:

```
AI_TRACE_CONTENT_MODE=metadata_only        # default - no content ever stored
AI_TRACE_CONTENT_MODE=redacted_preview     # redacted, truncated (500 char) previews stored
```

Changing this only affects **new** traces going forward - `ai_traces.content_mode` snapshots the mode active at write time on every row, so existing rows are never reinterpreted.

## Configuring custom redaction patterns

```
AI_TRACE_CUSTOM_REDACTION_PATTERNS='[{"name": "internal_case_id", "pattern": "CASE-\\d{6}"}]'
```

A JSON array of `{name, pattern}` objects (Python regex syntax). Invalid JSON or an invalid pattern is logged and ignored (fail-safe, not fail-closed on the whole redaction pipeline) - test new patterns against `apps/api/tests/test_ai_redaction.py`'s style before deploying.

## Running retention cleanup

```
python -m app.operations.observability_retention_cleanup [--retention-days N] [--dry-run]
```

- `--dry-run` reports how many trace rows would be deleted, without deleting anything - always run this first when changing `AI_TRACE_RETENTION_DAYS` or investigating unexpectedly high row counts.
- `--retention-days` overrides `AI_TRACE_RETENTION_DAYS` for a single run without touching the environment (e.g. a one-off tighter cleanup).
- Deletes child tables first (`ai_trace_stages`, `ai_retrieval_traces`, `ai_model_call_traces`, `ai_guardrail_traces`), then `ai_traces`, batched at 500 rows/iteration to avoid long-held locks.
- Exits 0 on success (including "nothing to delete"), 2 on an operational error (e.g. `--retention-days 0` or negative).

## Scheduling cleanup

Not bundled with an automatic scheduler in this pass. Add a cron entry or systemd timer calling the command above, alongside the existing `deployment/monitoring/check.sh` health-check cadence:

```
# Example: daily at 03:15
15 3 * * * cd /path/to/apps/api && python -m app.operations.observability_retention_cleanup >> /var/log/conversa/ai-trace-retention.log 2>&1
```

## Verifying redaction is working

`apps/api/tests/test_ai_redaction.py` covers every redaction category with crafted secret-shaped strings (Stripe keys, AWS keys, JWTs, bearer tokens, DB connection strings, emails, phone numbers, this codebase's widget keys and session tokens) plus custom-pattern loading and retention-mode behaviour. `apps/api/tests/test_ai_trace_no_secret_leakage.py` is an end-to-end test: it feeds a document containing a live-looking Stripe key and a database URL with an embedded password through the full `RAGOrchestrator.answer()` pipeline in `redacted_preview` mode, then scans every column of all five AI trace tables to assert the raw secret never appears. Run both before deploying a change to the redaction patterns.

## Privacy trade-offs (see also `AI_Trace_Data_and_Privacy_Policy.md`)

- `metadata_only` (default) gives zero content-leak surface but also zero content visibility for debugging - a deliberate default-safe choice.
- `redacted_preview` trades some content visibility (bounded to 500 chars, regex-redacted) for debuggability. Regex-based redaction is best-effort, not a formal guarantee - treat `redacted_preview` mode as "reduces risk," not "eliminates risk," and restrict `?include_content=true` access to `org_owner`/`client_admin` accordingly (already enforced).
- `encrypted_full_content` is not implemented - do not rely on it.
