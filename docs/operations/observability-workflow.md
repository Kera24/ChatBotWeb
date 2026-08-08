# Observability Workflow

How observability data flows from pre-release evaluation through production monitoring and back into the next release. This is the concrete, operational version of `docs/workflows/ai-development.md`'s "Observability" and "Production Evaluation" phases, applied continuously rather than per-change.

```
Offline Evaluation → Deployment → Telemetry → Dashboards → Alerts
  → Incident Detection → Root Cause Analysis → Golden Dataset Update
  → Regression Testing → Redeployment (loops back to Telemetry)
```

## Offline Evaluation

Every change passes the evaluation gate (`docs/architecture/evaluation.md`) before deployment — this is the pre-production baseline that production telemetry will later be compared against.

## Deployment

Per `docs/sops/deploying.md`. Release identity (git SHA, image digests, and — for AI changes — `prompt_version`/model/embedding identifiers) is recorded so any later trace can be attributed to exactly what was running.

## Telemetry

`docs/architecture/observability.md`'s 14-stage pipeline instrumentation captures every request: `ai_traces` (root), `ai_trace_stages`, `ai_retrieval_traces`, `ai_model_call_traces`, `ai_guardrail_traces`. Fail-safe by design — a telemetry failure never breaks the request it's attached to.

## Dashboards

`/observability` (dashboard + trace detail + retrieval debugger) surfaces request volume, latency percentiles, token/cost, fallback rate, blocked rate, evidence-insufficient rate, citation coverage — the human-facing view of the telemetry above.

## Alerts

Structured alert events fire on threshold breach (p95 latency, provider/embedding error rate, fallback rate, evidence-insufficient rate, invalid citation attempts, guardrail spikes, cost spikes, zero traffic) — see `docs/runbooks/observability-alerts.md` for the response process.

## Incident Detection

An alert, a dashboard anomaly, or a customer report identifies a problem. Deterministic 24h-vs-trailing-7-day-baseline drift signals (`docs/architecture/observability.md`) supplement threshold alerts for slower-moving degradation.

## Root Cause Analysis

Trace-level investigation: which stage, which guardrail layer, which model/prompt/retrieval version was involved. The trace model's per-stage granularity exists specifically to make this fast rather than requiring log archaeology.

## Golden Dataset Update

Real production failures become new evaluation cases (`docs/workflows/engineering-lifecycle.md` stage 20) — this is how the evaluation suite stays representative of actual usage rather than only the original pre-launch assumptions.

## Regression Testing

The fix (prompt, guardrail, retrieval, or model change) is validated against the full evaluation gate, including the newly-added case, before being considered done.

## Redeployment

The fix ships through the normal lifecycle (`docs/workflows/engineering-lifecycle.md`), and its own telemetry becomes the next iteration's baseline — closing the loop.

## Integration with other subsystems

- **Evaluation**: offline evaluation is the pre-deployment gate; production telemetry is the post-deployment check that the gate's predictions held. `docs/future/EvaluationV2.md`'s continuous evaluation will eventually merge these into one continuous signal.
- **Guardrails**: every layer A-H's verdict is traced (`ai_guardrail_traces`); a spike in a specific layer's block rate is itself an actionable observability signal, not just a guardrail-internal concern.
- **Graders**: advisory grader scores (`docs/engineering/graders.md`) are visible in evaluation run results; sustained score drift is a golden-dataset-update trigger even though grading itself isn't gating.
- **Prompt versions**: `prompt_key`/`prompt_version`/`prompt_hash` on every message make any quality shift traceable to an exact prompt version (`docs/runbooks/prompt-regressions.md`).
- **Model versions**: `ai_model_call_traces` records provider/model per call, making a model-attributable issue (`docs/runbooks/llm-provider-outage.md`, `docs/sops/model-failures.md`) immediately identifiable.
- **Embedding versions**: embedding provider/model/dimension changes are traceable through ingestion metadata, relevant when diagnosing a retrieval-quality shift that coincides with a re-embedding event.
- **Retrieval versions**: `ai_retrieval_traces` captures rank/similarity/selection/rejection-reason per chunk, making a retrieval-strategy change's effect (`docs/checklists/retrieval-checklist.md`) directly observable, not just theoretically evaluated.
