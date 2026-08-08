# SOP: Model Failures

## Purpose

Respond to a provider/model-level failure (outage, degraded quality, unexpected refusal/behavior pattern).

## When to use

`ai_model_call_traces` shows elevated error rate, latency, or `answer_state="failed"` attributable to the provider/model itself, not the surrounding pipeline.

## Step-by-step process

1. Confirm via `docs/runbooks/llm-provider-outage.md` whether this is an outage (route to that runbook) or a quality/behavior degradation (continue here).
2. For quality/behavior issues: pull representative failing traces, reproduce against the evaluation case set to quantify the regression.
3. If a fallback model/provider exists (`docs/future/ModelRouting.md`), route traffic away from the failing model while investigating.
4. If no fallback exists, the pipeline's existing fallback semantics (`answer_state="failed"`, `RAGProviderExecutionError`) already prevent silent bad answers — confirm this is functioning, don't build an emergency patch around it.
5. Escalate to the provider (support channel) if it's their-side degradation; otherwise treat as a model-selection/prompt issue via `docs/sops/prompt-failures.md`.

## Validation

Evaluation case set re-run against the model once the issue is understood; confirm `answer_state="failed"` handling worked correctly throughout (no silently wrong answers reached users).

## Rollback

Route away from the failing model/provider (routing config change) rather than attempting to patch around a provider-side issue.

## Success criteria

No user received a silently-wrong answer during the incident; root cause identified (provider-side vs. Conversa-side); routing/config restored once resolved.
