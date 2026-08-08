# Runbook: LLM Provider Outage

## Symptoms

`ai_model_call_traces` shows elevated error rate/timeouts from the generation provider; `answer_state="failed"` rate rising.

## Diagnosis

1. Confirm via the provider's own status page/API whether this is a provider-side outage.
2. Check `RAGProviderExecutionError` traces to confirm the pipeline's existing fallback semantics are functioning correctly (no silently-wrong answers reaching users during the outage).
3. Check if this is total (all requests failing) or partial (elevated error rate, some succeeding).

## Recovery

1. If `docs/future/ModelRouting.md` is implemented and a second provider exists: route traffic to the fallback provider.
2. If only one provider exists (current state — `docs/architecture/retrieval.md`): no failover is possible; confirm the pipeline is correctly surfacing `answer_state="failed"` rather than degrading silently, and wait out the provider's outage while monitoring their status.
3. Communicate proactively to affected tenants if the outage is prolonged.

## Validation

Error rate returns to baseline; `ai_model_call_traces` shows successful calls resuming.

## Escalation

Prolonged single-provider dependency risk is itself an argument for prioritizing `docs/future/ModelRouting.md` sooner — note this in the post-incident review.

## Post-incident review

How long were users affected with no fallback available? Feed this into `docs/engineering/implementation-order.md`'s prioritization of model routing if this recurs.
