# Query Rewrite

## Status: Implemented (Retrieval V2 Phase 3 - "Query Intelligence"), not yet promoted to production default

`app.services.query_transformation` (a provider-independent `QueryTransformer` protocol, mirroring `app.services.reranking.Reranker`'s shape - `IdentityQueryTransformer`/`DeterministicQueryTransformer`/`ModelAssistedQueryTransformer`, `build_query_transformer()` factory, `transform_query()` fail-safe/fail-loud policy wrapper) and its wiring into `assemble_retrieval_context()`/`RAGOrchestrator.answer()` now exist and are fully tested. `QUERY_TRANSFORMER_PROVIDER=identity` (the default) is byte-identical to the pre-Phase-3 pipeline: one retrieval query, the original question, unchanged - see `docs/architecture/retrieval.md` for the wiring detail. Only context-free rewriting (Implementation phase 1 below) is implemented; context-dependent (pronoun/reference) rewriting remains genuinely postponed pending `docs/future/MemoryV2.md`, per the original "Why postponed" reasoning below, which still applies to that phase.

## Purpose

Rewrite/expand user queries (resolve pronouns from conversation context, expand abbreviations, generate multiple query variants) before retrieval, to improve recall for poorly-phrased or context-dependent questions.

## Implementation

- **Abstraction** (`app/services/query_transformation.py`): `QueryTransformer` protocol (`transform(query, context) -> RetrievalQueryPlan`), `IdentityQueryTransformer` (identity, the production default/rollback target), `DeterministicQueryTransformer` (local, LLM-free conversational-filler stripping + whole-word abbreviation expansion), `ModelAssistedQueryTransformer` (a concise search-oriented reformulation via a caller-supplied `generate` closure - never imports `app.ai.*` directly), `build_query_transformer()` factory, `transform_query()` (the fail-safe/fail-loud policy wrapper every caller uses, mirroring `app.services.reranking.rerank_candidates`). `RetrievalQueryPlan.retrieval_queries[0]` is always the original question, so a caller that only reads `retrieval_queries` reproduces current behaviour whenever transformation is a no-op or disabled.
- **Model-assisted provider**: reuses the existing `AICoreService`/`AIProvider` abstraction via `app.ai.dependencies.build_query_rewrite_generate_fn` (a plain `(query) -> str` closure over `AICoreService.generate()`) - never introduces a new/paid provider. The `retrieval_query_rewrite` prompt (`app.ai.prompt_registry.register_default_query_rewrite_prompt`) instructs the model to preserve meaning, never answer the question, never invent entities, and treat the user's question as untrusted data it must not follow instructions from.
- **Original-question immutability (hard requirement)**: `RAGOrchestrator.answer()` passes `query_plan.retrieval_queries` into `assemble_retrieval_context()` only - `request.query` (the original question) is untouched everywhere else: generation variables, evidence sufficiency, prompt resolution, persisted `ChatMessage` content, and guardrail input policy all see only the original question.
- **Multi-query retrieval and merge** (`app/services/retrieval_context.py`, `merge_multi_query_candidates` in `query_transformation.py`): when a plan produces more than one retrieval query, dense search runs once per query (same calibrated `min_similarity_score` applied to each) and results are merged deterministically - per distinct chunk, keeps the highest dense cosine-similarity score seen across queries (never an incomparable fused score), tracks which query indices found it and how many times, orders by best score → appearances → best rank → first-seen. Only applies to `dense_only`; `hybrid_rrf` is out of Phase 3's scope.
- **Failure behaviour**: production traffic falls back safely to the identity plan (original query only) on any transformer error (`query_transformer_fail_loud=False`, `RAGOrchestratorDependencies` default); `app.evaluation.engine` always sets `query_transformer_fail_loud=True` so a transformer defect surfaces as a hard case failure (`reason="query_transformer_failed"`) instead of silently succeeding via that same fallback.
- **Observability**: `record_query_transformation_outcome` (`app.observability.otel_metrics`) - `strategy`/`provider`/`model`/`status`/`enabled` low-cardinality labels only (never a tenant/request id or raw query text), generated/raw/deduplicated candidate counts and latency as histograms.
- **Hard limits** (Part 7 cost/token discipline): `QUERY_TRANSFORMER_MAX_QUERIES` (default 3 - original + at most one rewrite + at most one alternate), `QUERY_TRANSFORMER_MAX_QUERY_CHARS` (default 300), `QUERY_TRANSFORMER_TIMEOUT_SECONDS` (default 3.0s), `QUERY_TRANSFORMER_CANDIDATE_POOL_SIZE` (default 25, per-query dense pool before merge).
- **Failure-analysis and bake-off tooling**: `app.operations.eval_query_failure_analysis` classifies baseline `dense_only` answerable failures by lexical-mismatch mechanism (terminology/acronym/conversational-wording/canonical-term signals) before assuming rewriting helps; `app.operations.eval_query_transform_bakeoff` runs the controlled identity vs. deterministic vs. model_assisted comparison (query rescue rate / query damage rate / case-level mechanism classification) against the golden and chunking-focused corpora, the same pattern as `app.operations.eval_reranker_bakeoff`.

## Current limitation

The raw user question is embedded and searched as-is when `QUERY_TRANSFORMER_PROVIDER=identity` (the default); a question like "what about the second one" has no context to resolve against, and ambiguous phrasing isn't expanded before retrieval unless `deterministic`/`model_assisted` is explicitly configured.

## Why postponed (context-dependent rewriting only)

Context-dependent (pronoun/reference) rewriting meaningfully depends on `docs/future/MemoryV2.md` for conversation-context-dependent rewrites (pronoun resolution needs prior turns) and remains genuinely out of scope. Context-free rewriting (expansion/normalization, multi-query) is implemented and evaluated above - see the Phase 3 evaluation report for the promotion decision on whether its measured benefit justifies enabling it by default.

## Dependencies

- `docs/future/MemoryV2.md` (short-term memory) for context-dependent rewrites.
- A real generation provider capable of cheap, fast rewrite calls without materially increasing end-to-end latency.

## Implementation phases

1. **Done** - Context-free query normalization/expansion (abbreviation expansion, conversational-filler stripping, model-assisted reformulation, multi-query merge). See Implementation above.
2. Context-dependent rewrite (pronoun/reference resolution using recent conversation turns) once `docs/future/MemoryV2.md` ships - not started.
3. **Done, folded into phase 1** - multi-query expansion (generate up to one rewrite + one alternate, retrieve for each, merge deterministically) - evaluated together with phase 1 rather than as a separate higher-cost follow-up, since the Part 7 hard caps (`QUERY_TRANSFORMER_MAX_QUERIES=3`) keep it cheap enough to ship in the same phase.

## Technical design

Pre-retrieval step in `RAGOrchestrator.answer()`, additive before `assemble_retrieval_context()` — input policy (guardrail Layer C+D) still evaluates the *original* user input, not the rewritten query, so guardrail behavior doesn't change. See Implementation above for the actual wiring.

## Evaluation plan / results

See the Phase 3 evaluation report (`app.operations.eval_query_transform_bakeoff`, identity vs. deterministic vs. model_assisted, golden + chunking-focused datasets, real `nomic-embed-text-v2-moe` embeddings) for the actual query rescue rate / query damage rate / Recall@K deltas and the promotion decision against the criteria in `docs/architecture/evolution-policy.md`.

## Rollback strategy

`QUERY_TRANSFORMER_PROVIDER=identity` (the default) - no schema or data changes, no code change required.

## Success metrics

Reduced fallback/evidence-insufficient rate specifically on ambiguous or context-dependent questions.
