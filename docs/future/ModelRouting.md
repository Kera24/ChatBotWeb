# Model Routing

## Purpose

Route requests to different models/providers based on request characteristics (cost sensitivity, complexity, assistant configuration) once more than one live provider exists.

## Current limitation

`app.ai.provider_registry.ProviderRegistry` supports multiple providers architecturally, but only `MockAIProvider` is implemented (`docs/architecture/retrieval.md`) — there is nothing to route between yet.

## Why postponed

Routing logic is meaningless with a single implemented provider; needs at least one real (non-mock) provider live before routing has any decision to make.

## Dependencies

- At least two live providers/models registered in `ModelRegistry`.
- Cost/quality trace data (`docs/architecture/observability.md`'s `ai_model_call_traces`) to base routing decisions on evidence rather than guesswork.

## Implementation phases

1. Ship a second real provider (beyond the first live provider) so routing has an actual choice to make.
2. Static per-assistant model configuration first (an admin picks a model per assistant) — simplest possible routing, no dynamic logic yet.
3. Dynamic routing (cost/complexity-based selection per request) as a later, evidence-driven phase, only if static configuration proves insufficient.

## Technical design

Routing decision happens in `AICoreService.generate()` (`app.ai.service`) before the provider call, selecting from `ProviderRegistry` — the RAG pipeline stages before and after generation are unaffected.

## Evaluation plan

Compare answer quality and cost across routing strategies (static vs. dynamic) on the evaluation case set; verify routing doesn't introduce inconsistent behavior for otherwise-identical requests.

## Rollback strategy

Static per-assistant configuration is trivially reversible (change the config). Dynamic routing should ship behind a flag with static configuration as the always-available fallback.

## Success metrics

Cost reduction and/or quality improvement attributable to routing, measured against a single-model baseline, with no evaluation-gate regression.
