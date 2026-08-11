# Reranking

## Status: Implemented (Retrieval V2 Phase 2), not yet promoted to production default

`app.services.reranking` (a provider-independent `Reranker` protocol, mirroring `app.services.embeddings.EmbeddingProvider`'s shape) and its wiring into `assemble_retrieval_context()`/`RAGOrchestrator` now exist and are fully tested. `RERANKER_PROVIDER=none` (the default) is byte-identical to the pre-reranking pipeline - see `docs/architecture/retrieval.md` for the wiring detail and the Phase 2 evaluation report for the promotion decision. This section is retained (rather than deleted) because the original spec below still describes the feature's purpose and evaluation plan accurately; only "postponed"/"current limitation" are now stale.

## Purpose

Add a second-pass reranking step over an already-retrieved dense candidate pool to improve final chunk selection precision beyond single-pass vector similarity ranking.

## Implementation

- **Abstraction** (`app/services/reranking.py`): `Reranker` protocol (`rerank(query, candidates, top_k) -> RerankOutcome`), `NoOpReranker` (identity, the production default/rollback target), `CrossEncoderReranker` (local sentence-transformers cross-encoder), `build_reranker()` factory, `rerank_candidates()` (the fail-safe/fail-loud policy wrapper every caller uses).
- **Model chosen**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (default `RERANKER_MODEL`). ~80MB, 6-layer MiniLM cross-encoder trained on MS MARCO passage ranking, Apache-2.0 licensed, CPU-inference-friendly (no GPU required) - fits the single-low-cost-VPS deployment target (`docs/architecture/deployment.md`) without adding a new paid API dependency. Live-validated in this environment: loads in ~60s cold (one-time HuggingFace download, then cached), correctly ranks a real relevance-vs-irrelevance pair by a wide margin (see the Phase 2 evaluation report).
  - Alternatives considered: `BAAI/bge-reranker-v2-m3` (stronger, multilingual, but ~568M params - materially heavier CPU latency/memory footprint than justified without evidence the smaller model is insufficient); an LLM-prompt-based "reranker" using the existing Ollama/OpenRouter generation providers (rejected - conflates the reranking and generation provider abstractions, and a real cross-encoder is cheaper and faster per candidate than an LLM completion call per candidate).
- **Pipeline** (`app/services/retrieval_context.py`): when a non-`NoOpReranker` is active, the dense search widens to `RERANKER_DENSE_CANDIDATE_POOL_SIZE` (default 25, still gated by the calibrated `RETRIEVAL_MIN_SIMILARITY_SCORE`) before reranking down to `RERANKER_FINAL_TOP_K` (default = `RETRIEVAL_MAX_CONTEXT_CHUNKS`). Dense cosine-similarity score (`VectorSearchMatch.score`) is never overwritten by the rerank score - evidence-sufficiency's off-topic threshold stays calibrated against the same scale it always was.
- **Failure behaviour**: production traffic falls back safely to unmodified dense ordering on any reranker error (`reranker_fail_loud=False`, `RAGOrchestratorDependencies` default); `app.evaluation.engine` always sets `reranker_fail_loud=True` so a reranker defect surfaces as a hard case failure (`reason="reranker_failed"`) instead of silently succeeding via that same fallback.
- **Observability**: `record_reranker_outcome` (`app.observability.otel_metrics`) - `reranker_enabled`/`provider`/`model`/`status` low-cardinality labels, candidate/selected counts and latency as histograms.

## Dependencies

- A real (non-mock) local cross-encoder model - `sentence-transformers` (optional dependency; the abstraction and its unit tests do not require it - only `CrossEncoderReranker`'s live path does).

## Evaluation plan / results

See the Phase 2 evaluation report (dense_only vs. dense+reranker, golden + chunking-focused datasets, real `nomic-embed-text-v2-moe` embeddings) for the actual Precision@K/Recall@K/pass-rate deltas and the promotion decision against the criteria in `docs/architecture/evolution-policy.md`.

## Rollback strategy

`RERANKER_PROVIDER=none` (the default) - no schema or data changes, no code change required.
