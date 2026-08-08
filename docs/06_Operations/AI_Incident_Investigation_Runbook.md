# AI Incident Investigation Runbook

Status: implemented

## Scope

Use this runbook when investigating a specific AI-serving incident: a customer-reported bad answer, a spike in fallback/blocked/failed rates, a cost spike, or an alert from `AI_Alert_Threshold_Guide.md`. For infrastructure-level incidents (container down, database unreachable), see `Azure_Monitoring_and_Alerting_Runbook.md` and `Backup_and_Restore_Runbook.md` instead.

## Step 1: Find the trace

- **From a customer report with a conversation ID or timestamp**: `GET .../observability/traces?conversation_id=...` or filter by `started_after`/`started_before` on the dashboard.
- **From an X-Trace-ID / X-Request-ID header** (authenticated dashboard requests echo `X-Trace-ID`; the public widget response includes `request_id`): look up by `trace_id` directly at `/observability/traces/{traceId}`, or cross-reference `request_id` via the list filter.
- **From an alert event**: alerts report aggregate rates, not individual traces - use the same time window and filter by `answer_state`/`status` to find the specific traces that drove the rate up.

## Step 2: Read the timeline

Open the trace detail page and read the 14-stage timeline top to bottom (see `Retrieval_Debugger_Guide.md`'s "Reading a trace end-to-end" section). The first stage with `status != "ok"` is where the request's behaviour was decided:

| Stage status | What it means |
|---|---|
| `blocked` on `input_policy` | A guardrail rejected the query before retrieval even ran - check `reason_code`, likely a prompt-injection or scope violation. |
| `empty` on `retrieval` | No chunks matched - check the assistant's knowledge scope and whether the relevant document is actually ingested and embedded. |
| `blocked` on `citation_validation` | Citations resolved outside the allowed document scope - should essentially never fire (defence-in-depth only); if it does, treat as a priority investigation into the retrieval scoping logic itself. |
| `blocked` on `evidence_sufficiency` | Evidence was retrieved but didn't support the specific fact asked - expected/correct behaviour for many "not in the knowledge base" questions, not necessarily a bug. |
| `error` on `provider_generation` | The AI provider call failed - check `ai_model_call_traces.error_code` and the model call breakdown panel. |
| `blocked` on `output_sanitisation` | The generated answer failed a post-generation safety check (markup, secret/prompt leakage) and was replaced with a fallback. |

## Step 3: Check guardrails and retrieval

- **Guardrail outcomes panel**: confirms which of the 5 layers (A-H) fired and why.
- **Retrieval debugger panel**: what was actually retrieved and selected, with similarity scores (see `Retrieval_Debugger_Guide.md`'s caveat about mock-provider scores being non-semantic).

## Step 4: Check cost and token usage

Model call & cost breakdown panel: provider/model, prompt version, token counts, and cost (or explicitly "unknown" - never a misleading $0). If pricing shows "unknown," check whether `ModelConfig` for the model in question has `input_cost_per_million_tokens`/`output_cost_per_million_tokens` configured.

## Step 5: Correlate with OTel (if enabled)

If `otel_trace_id` is populated on the trace summary, and OTLP export or Azure Monitor is active, use that ID to pivot into Tempo (VPS stack) or Application Insights (Azure) for infra-level span detail (DB query timing, HTTP-level spans) alongside the AI-specific trace. This is a join key, not a replacement - the AI trace tables remain the source of truth for guardrail/retrieval/cost detail.

## Step 6: Determine if this is a pattern

Check `/observability`'s trend signals (24h vs. 7-day baseline) and `GET .../observability/anomalies` for whether the specific trace is part of a broader shift (e.g. `fallback_rate` or `evidence_insufficient_rate` trending up) versus an isolated case.

## Step 7: Escalate correctly

- **Individual incorrect answer, guardrails all passed**: route to the review queue (existing conversations/review workflow) for human quality review - do not label it "hallucination rate" in any report; use "review-confirmed incorrect answer" only after a human confirms it (see `AI_Metrics_Dictionary.md`'s terminology rule).
- **Guardrail false-positive (blocking legitimate questions)**: file against the relevant guardrail module (`app.ai.guardrails.*`) with the trace_id and reason_code as reproduction evidence.
- **Cost or latency spike**: check `AI_Alert_Threshold_Guide.md`'s thresholds and whether traffic volume, not per-request cost, changed.
- **Suspected data leak in a trace preview**: this is a privacy incident - see `AI_Trace_Data_and_Privacy_Policy.md`'s redaction guarantees, and if a real gap is confirmed, treat it with the same urgency as any other PII/secret exposure incident, independent of this runbook.

## Retention window caveat

Traces older than `AI_TRACE_RETENTION_DAYS` (default 90) are deleted (see `AI_Trace_Retention_and_Redaction_Guide.md`). For older incidents, fall back to `ChatMessage`/`Citation` rows (which follow their own, separate, typically longer retention) via the existing Conversations view.
