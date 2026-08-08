# AI Metrics Dictionary

Status: implemented

## Terminology rule

These are deterministic, rule-based signals derived from guardrail and retrieval outcomes already computed by `app.ai.rag_orchestrator.RAGOrchestrator` - never a claim about whether an answer was factually correct. Nothing in this system is labelled "hallucination rate." Use one of:

- **unsupported-answer signal** - a general term for "the system could not confirm this answer was grounded," without claiming it was wrong.
- **grounding failure** - a specific, review-confirmed case where the grounding/evidence checks should have caught an issue and didn't (requires human review to assert, not just to observe a metric).
- **evidence-insufficient response** - the deterministic, always-available metric below: evidence sufficiency guardrail blocked the request.
- **review-confirmed incorrect answer** - only ever assigned after a human (review queue, evaluation grading) confirms it. Never derived automatically.

## Dashboard metrics (`GET .../observability/metrics`)

| Metric | Definition | Source |
|---|---|---|
| `request_volume` | Count of AI traces in the filtered window. | `ai_traces` count |
| `p50_latency_ms` / `p95_latency_ms` | Percentile of `total_latency_ms` across traces with a non-null value. Computed in Python over the filtered result set (not a streaming/approximate percentile system - fine at controlled-pilot scale). | `ai_traces.total_latency_ms` |
| `total_tokens` | Sum of `total_tokens` across traces. | `ai_traces.total_tokens` |
| `total_estimated_cost` | Sum of `estimated_cost` across traces with a known price. `null` if no trace in the window has known pricing. | `ai_traces.estimated_cost` |
| `unknown_cost_request_count` | Count of completed traces where cost is unknown (no price configured for the model used) - never silently counted as $0. | `ai_traces.estimated_cost IS NULL` |
| `answered_count` | Count where `answer_state == "answered"`. | `ai_traces.answer_state` |
| `fallback_count` | Count where `fallback_used` is true **and** no guardrail layer blocked the request (i.e. a non-guardrail fallback such as empty retrieval). | `ai_traces` + `ai_guardrail_traces` |
| `blocked_count` | Count of distinct traces with at least one guardrail layer where `blocked = true`. | `ai_guardrail_traces` |
| `failed_count` | Count where `answer_state == "failed"` or trace `status == "failed"` (e.g. provider execution error, tenant-resolution error). | `ai_traces` |
| `fallback_rate` / `blocked_rate` / `provider_failure_rate` | Respective count divided by `request_volume`. | derived |
| `citation_coverage` | Fraction of *answered* traces that have at least one `ai_retrieval_traces` row with `selected = true`. `null` if there were no answered traces in the window. | `ai_retrieval_traces` |
| `evidence_insufficient_rate` | Fraction of all traces with a blocked `evidence_sufficiency` guardrail row. | `ai_guardrail_traces` |

## Guardrail layers (A-H)

Matches the inline comments in `RAGOrchestrator.answer()`:

| Layer | Guardrail name | What it checks |
|---|---|---|
| C+D | `input_policy` | Capability/intent boundaries and direct prompt-injection defence, before retrieval or generation. |
| — | `query_embedding` / `retrieval` (stages, not guardrails) | Vector search against the assistant's scoped knowledge. |
| F | `citation_policy` | Defence-in-depth assertion that retrieved citations are within the allowed document scope. |
| E | `document_sanitizer` | Strips injected-instruction-style text from retrieved document content before it reaches the model. |
| A+B | `evidence_sufficiency` | Whether retrieved evidence supports the *specific* fact asked, not just the general topic. |
| — | `grounding` | **Not wired into the live pipeline** - recorded as a `skipped` stage with reason `not_wired_into_pipeline`, never fabricated as pass/fail. |
| G+H | `output_safety` | Post-generation: markup neutralisation and secret/prompt-leakage pattern detection, before persistence or return. |

## Anomaly / drift signals (`GET .../observability/anomalies`)

Deterministic threshold-based comparisons of the trailing 24h window against the preceding 7-day baseline (the 7 days immediately before that 24h window). Not machine learning. Each signal reports `baseline_value`, `current_value`, `relative_change_pct`, and whether it `triggered` (`|relative_change_pct| >= threshold_pct`, default 25%):

`fallback_rate`, `blocked_rate`, `p95_latency_ms`, `cost_per_request`, `citation_coverage`, `evidence_insufficient_rate`, `request_volume`.

## Alert events (`GET .../observability/alerts`)

See `AI_Alert_Threshold_Guide.md` for the full threshold list and configuration.
