# AI System Design

Covers embedding strategy, generation strategy, fallback strategies, model routing, and provider abstraction. Companion document `docs/engineering/ai-lifecycles.md` covers the request-flow lifecycles (prompt, context assembly, retrieval, memory, evaluation, guardrail, production feedback).

## Embedding strategy

**Current**: single configured provider (`EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION`), applied uniformly at ingestion time (`app.services.embeddings.embed_document_version_chunks()`) and at query time (same provider, so query and chunk vectors are always comparable). See `docs/architecture/knowledge-ingestion.md` and `docs/architecture/vector-storage.md`.
**Future**: multi-provider comparison before any change (`docs/future/EmbeddingBakeoff.md`); embedding-dimension changes always require full re-embedding, never an in-place reinterpretation of existing vectors.

## Generation strategy

**Current**: single `AIProvider` implementation (`MockAIProvider`) behind `app.ai.provider_registry.ProviderRegistry`, invoked once per request from `AICoreService.generate()`. No live OpenAI/Anthropic/Azure OpenAI integration exists yet. See `docs/architecture/retrieval.md`'s "Providers" section.
**Future**: first live provider, then `docs/future/ModelRouting.md` once more than one exists.

## Fallback model strategy

**Current**: there is no secondary *model* to fall back to (only one provider exists) — what exists today is answer-level fallback: any guardrail block or empty retrieval routes through `RAGOrchestrator._persist_fallback()`, always persisting `answer_state="fallback"` with a `guardrail_reason_code`, never silently dropping the turn. A provider *execution failure* persists `answer_state="failed"` and raises `RAGProviderExecutionError`. See `docs/architecture/retrieval.md`'s "Fallback semantics."
**Future**: once a second provider/model exists, provider-failure fallback (route to a secondary model on provider error, distinct from guardrail-triggered answer fallback) becomes possible — this is a new capability, not yet designed, and would need its own evaluation plan before being trusted.

## Embedding fallback strategy

**Current**: none — a single embedding provider is a hard dependency; if it fails, ingestion and retrieval both fail (fail loud, not silent, per `docs/architecture/knowledge-ingestion.md`'s lifecycle-transition-failure visibility).
**Future**: not currently planned as a distinct feature; would only become relevant alongside `docs/future/EmbeddingBakeoff.md` if multiple embedding providers become simultaneously supported (not just compared).

## Model routing

**Current**: not applicable — `ProviderRegistry` supports registering multiple providers architecturally, but only one is implemented, so there is nothing to route between. See `docs/future/ModelRouting.md`.
**Future**: static per-assistant model configuration first, dynamic cost/complexity-based routing later, both gated on a second live provider existing.

## Future provider abstraction

**Current**: `app.ai.providers.base.AIProvider` is the interface every provider (mock or real) must implement; `ProviderRegistry`/`ModelRegistry` (`app.ai.model_registry`) are where a new provider gets registered — the orchestrator never special-cases a specific provider by name. This abstraction is what keeps `docs/principles/engineering-principles.md`'s vendor-independence principle real rather than aspirational.
**Future**: `docs/future/GPUWorkers.md` (self-hosted models) and `docs/future/ModelRouting.md` both build on this same interface without requiring it to change shape.

## Adding a new provider

Implement `AIProvider` exactly, register it in `ProviderRegistry`/`ModelRegistry` with correct `input_cost_per_million_tokens`/`output_cost_per_million_tokens`/`cost_calc_version` (never silently treat unknown pricing as `$0` — see `docs/architecture/observability.md`'s cost-accounting rules), and validate against the full evaluation case set before it can be selected for any tenant traffic.
