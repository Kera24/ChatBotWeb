# RAG Pipeline — Current / Future / Out of Scope

## Current

Single entry point `RAGOrchestrator.answer()`, one pipeline for both authenticated and public-widget requests, guardrail layers A-H interleaved with retrieval/generation, fallback-not-silent-failure semantics. Full detail: `docs/architecture/retrieval.md`. Decision record: ADR 0004 (RAG orchestrator boundary).

## Future

- Hybrid retrieval, reranking, query rewrite — see `docs/future/HybridRetrieval.md`, `docs/future/Reranking.md`, `docs/future/QueryRewrite.md`.
- A real (non-mock) LLM provider — see `docs/architecture/retrieval.md`'s "Providers" section and `docs/adr/0002-provider-abstraction.md`.
- Semantic caching of near-duplicate queries — see `docs/future/CachingV2.md`.

## Out of scope (not planned)

- Per-channel forks of the orchestrator logic (e.g. a "widget-only" or "Slack-only" pipeline) — one core pipeline stays the invariant regardless of channel count.
