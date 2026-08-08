# Cost Optimisation

## Purpose

Reduce per-request AI cost (provider token spend, infrastructure) once real usage volume and a live provider make cost a meaningful, measurable target.

## Current limitation

Cost accounting exists (`ModelConfig.input_cost_per_million_tokens`/`output_cost_per_million_tokens`, `ai_model_call_traces` — `docs/architecture/observability.md`) but there's no live provider yet, so real cost data doesn't exist to optimize against; only `MockAIProvider` is implemented.

## Why postponed

Optimization needs a real cost baseline first. Billing usage-based pricing (`docs/engineering/billing.md`'s future item) also depends on the same real-provider cost data — the two are linked and both wait on the same dependency.

## Dependencies

- A live (non-mock) AI provider generating real token-cost data.
- `docs/architecture/observability.md`'s cost aggregation (currently computed on-read via `GROUP BY`, no rollup table yet).

## Implementation phases

1. Establish a real cost baseline once a live provider ships (per-request, per-tenant, per-model cost visibility already exists structurally — just needs real data).
2. Identify highest-cost patterns from observability data (long prompts, repeated near-duplicate queries, over-large retrieval `top_k`).
3. Apply targeted optimizations: `docs/future/SemanticCache.md` and `docs/future/CachingV2.md` for redundant-work reduction, `docs/future/ModelRouting.md` for cost-aware model selection, prompt-length reduction via `docs/future/PromptOptimisation.md`.
4. Tie cost data into billing (`docs/engineering/billing.md`'s usage-based billing future item) once the cost signal is trustworthy enough to charge against.

## Technical design

No new cost-tracking infrastructure needed — this uses the existing `ai_model_call_traces`/`ai_traces` cost fields; optimization work happens in the consuming features (caching, routing, prompt design) listed above, not in a new "cost optimizer" module.

## Evaluation plan

Track cost-per-conversation and cost-per-tenant trends before/after each optimization; ensure no optimization degrades evaluation-gate scores in pursuit of lower cost.

## Rollback strategy

Each contributing optimization (caching, routing, prompt changes) has its own rollback plan; cost optimization itself has no separate rollback mechanism beyond reverting whichever underlying change caused a regression.

## Success metrics

Measured cost-per-conversation reduction over time with no evaluation-gate regression, feeding into `docs/engineering/billing.md`'s future usage-based pricing model.
