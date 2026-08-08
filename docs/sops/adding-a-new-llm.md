# SOP: Adding a New LLM

## Purpose

Add a new generation provider/model without breaking the existing `AIProvider` abstraction or evaluation guarantees.

## When to use

A new provider (OpenAI/Anthropic/Azure OpenAI/self-hosted) needs to be available for selection, per `docs/architecture/retrieval.md`'s "Providers" section and `docs/future/ModelRouting.md`.

## Step-by-step process

1. Follow the Generation Models workflow in `docs/workflows/ai-development.md` (Research → Prototype → Offline Evaluation → ...).
2. Implement `app.ai.providers.base.AIProvider` exactly — no orchestrator special-casing.
3. Register in `ProviderRegistry`/`ModelRegistry` (`app.ai.model_registry`) with correct `input_cost_per_million_tokens`/`output_cost_per_million_tokens`/`cost_calc_version` — never leave pricing unset and silently treated as `$0`.
4. Run the full evaluation case set against the new provider (`docs/checklists/evaluation-checklist.md`).
5. Shadow-test against redacted production query samples before serving live.
6. Gradual rollout (single-provider swap, or via `docs/future/ModelRouting.md` if a second provider already exists).

## Validation

`docs/checklists/rag-checklist.md` and `docs/checklists/evaluation-checklist.md` in full; cost fields verified populated in `ai_model_call_traces`.

## Rollback

Provider-abstraction-based: revert `ProviderRegistry` selection to the prior provider — a config change, not a code rollback.

## Success criteria

Evaluation gate passes with no regression; cost accounting accurate; provider selectable/deselectable via configuration alone.
