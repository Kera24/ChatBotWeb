# Retrieval / RAG Pipeline Architecture

The single entry point is `app.ai.rag_orchestrator.RAGOrchestrator.answer()`. Both the authenticated dashboard-test path (`app/api/v1/workspaces.py::answer_workspace_rag_question`) and the public widget path (`app.access.messages.rag_adapter.PublicWidgetRAGAdapter`) call the exact same orchestrator — do not fork this logic per channel.

## Pipeline stages, in order

1. Workspace/tenant validation, assistant/conversation resolution.
2. **Input policy** (guardrail Layer C+D) — `app.ai.guardrails.input_policy.evaluate_input_policy()`. Blocks before retrieval or generation ever run.
3. **Query embedding + vector retrieval** — `app.services.retrieval_context.assemble_retrieval_context()`, backed by `app.services.vector_search`. See `vector-storage.md`.
4. **Citation policy** (Layer F) — `app.ai.guardrails.citation_policy.verify_citations()`, defence-in-depth assertion that citations stay within the allowed document scope.
5. **Document sanitization** (Layer E) — `app.ai.guardrails.document_sanitizer.sanitise_evidence_content()`, strips injected-instruction-style text from retrieved chunks before they reach the model.
6. **Evidence sufficiency** (Layer A+B) — `app.ai.guardrails.evidence_sufficiency.verify_evidence_sufficiency()`, checks the evidence supports the *specific* fact asked, not just the general topic.
7. **Prompt construction** — inside `AICoreService.generate()` (`app.ai.service`), via `app.ai.prompt_registry.PromptRegistry.render()` (corrected: this stage does not call `app.services.prompt_assembly.assemble_grounded_prompt()` — that function backs only the separate preview-only `POST /{workspace_id}/retrieval/prompt` endpoint, a pre-existing distinction now documented in `docs/architecture/prompts.md`'s "Known, pre-existing drift" section). Just before this stage, `RAGOrchestrator.answer()` additionally calls `app.prompts.resolution.resolve_composite_prompt()` — if the widget's workspace has an active DB-backed prompt deployment (or a live experiment), its rendered output is passed through as `AICoreGenerateInput.override_rendered_prompt` and used instead of the code-defined default; a dormant scope is unaffected. See `docs/architecture/prompts.md`.
8. **Provider call** — `self.ai_core.service.generate()`.
9. **Output safety** (Layer G+H) — `app.ai.guardrails.output_safety.check_output_safety()`, markup neutralization + secret/prompt-leakage detection, before persistence or return.
10. Persistence — `app.services.conversation.append_assistant_message`/`attach_citations_to_assistant_message`.

See `guardrails.md` for the full A-H layer reference and `observability.md` for how every stage above is traced.

## Knowledge scoping

Each assistant (`Widget`) has a `knowledge_scope_json` (list of document IDs) on its current configuration draft/revision. `document_ids=None` in `search_embedded_chunks` means "no scope restriction" (raw workspace-level query, no assistant selected); `document_ids=[]` means an assistant WAS resolved and its scope is explicitly empty — this must retrieve **zero** chunks, never fall back to "everything." This distinction is security-critical; do not collapse it.

## Providers

`app.ai.provider_registry.ProviderRegistry` / `app.ai.providers.base.AIProvider`. **Only `MockAIProvider` is implemented today** (`app.ai.providers.mock`) — deterministic hash-based fake responses, real token-count estimation. No live OpenAI/Anthropic/Azure OpenAI provider exists yet. If asked to add one, follow the `AIProvider` interface exactly and register it in `ProviderRegistry`/`ModelRegistry` (`app.ai.model_registry`) rather than special-casing it in the orchestrator.

## Cost accounting

`ModelConfig` (`app.ai.model_registry`) carries `input_cost_per_million_tokens`/`output_cost_per_million_tokens` (nullable — unknown pricing must never be silently treated as `$0`) and `cost_calc_version` (bump manually when pricing changes). `app.ai.accounting.AIUsageAccountingService` computes per-call cost; this ledger is in-memory only (not persisted) — durable per-message cost lives on `ChatMessage`, and durable per-request trace-level cost lives in `ai_model_call_traces` (see `observability.md`).

## Fallback semantics

Any guardrail block or empty retrieval routes through `RAGOrchestrator._persist_fallback()`, which always persists a real assistant message with `answer_state="fallback"` and a `guardrail_reason_code` in metadata — never silently drops the turn. A provider execution failure persists `answer_state="failed"` and raises `RAGProviderExecutionError` (caught and mapped to an HTTP error by the caller).

## Hybrid retrieval (Retrieval V2 Phase 1)

`assemble_retrieval_context()` supports two strategies via `settings.RETRIEVAL_STRATEGY` (or a per-request `RAGOrchestrationRequest.retrieval_strategy` override, used by the evaluation engine): `dense_only` (default, unchanged behavior) and `hybrid_rrf` (dense + `app.services.lexical_search` PostgreSQL full-text candidates, fused via `app.services.retrieval_fusion.reciprocal_rank_fusion()`). **`dense_only` remains the production default** — see ADR-0033: a real-embedding controlled bake-off (`nomic-embed-text-v2-moe`, threshold 0.32, both `golden_dataset.json` and the 104-case `chunking_dataset.json`) showed `hybrid_rrf` does not materially improve recall on the corpus purpose-built to test the retrieval-recall gap, so it was not promoted. `hybrid_rrf` is fully implemented, tested (unit, real PostgreSQL integration tier, orchestrator end-to-end), and available as a one-line config change for future reconsideration.

Fused candidates keep `RetrievalCitationData.score` = the dense cosine-similarity score when a dense channel match exists (else `0.0` for a lexical-only match) — the RRF score itself is never substituted in, since `evidence_sufficiency`'s off-topic detector is calibrated for the cosine scale. RRF score/channel provenance is exposed separately via `RetrievalContextResult.retrieval_debug` (`RetrievalDebugInfo`) and `RAGOrchestrationResult.metadata`, never fed into any guardrail.

`app.evaluation.embedding_cache.CachingEmbeddingProvider` (default-on via `EvaluationRunOptions.embedding_cache_enabled`) memoises `embed()` by exact `(provider, model, dimension, content-hash)` inside `run_evaluation()` only — SQLite's no-vector-index retrieval path otherwise re-embeds every candidate chunk on every case. Evaluation-only; never touches production retrieval.

## Query transformation (Retrieval V2 Phase 3)

Before retrieval, `RAGOrchestrator.answer()` calls `app.services.query_transformation.transform_query()` on `request.query`, producing a `RetrievalQueryPlan` (`retrieval_queries[0]` is always the original question). Only `query_plan.retrieval_queries` is passed into `assemble_retrieval_context()` — `request.query` itself is never replaced anywhere else (generation variables, evidence sufficiency, prompt resolution, persisted `ChatMessage` content, guardrail input policy). Controlled by `settings.QUERY_TRANSFORMER_PROVIDER` (or a per-request override): `identity` (default, unchanged behavior — one retrieval query), `deterministic` (local, LLM-free conversational-filler stripping + abbreviation expansion), `model_assisted` (a concise reformulation via the existing `AICoreService`/`AIProvider` abstraction, never a new provider). **`identity` remains the production default** — see the Phase 3 evaluation report for the promotion decision.

When a plan produces more than one retrieval query (`dense_only` strategy only — never `hybrid_rrf`), `assemble_retrieval_context()` runs dense search once per query and merges results via `app.services.query_transformation.merge_multi_query_candidates()`: per distinct chunk, keeps the highest dense cosine-similarity score seen across queries (never an incomparable fused score — same calibrated-threshold-comparable scale `evidence_sufficiency` relies on), orders by best score → appearances → best rank → first-seen. Query-transformer provenance (strategy/provider/model/status/latency/query counts) is exposed via `RetrievalContextResult.retrieval_debug` and `RAGOrchestrationResult.metadata`, never fed into any guardrail, never placed in a Prometheus label (see `observability.md`'s cardinality policy).

Production traffic falls back safely to the identity plan on any transformer error (`query_transformer_fail_loud=False`); `app.evaluation.engine` sets this `True` so a transformer defect surfaces as a hard case failure (`reason="query_transformer_failed"`) instead of silently succeeding via the same fallback. See `docs/future/QueryRewrite.md` for the full design and evaluation report.

## Adding a new stage or changing pipeline behavior

- Add stages/checks as additive steps in `answer()`, after the value they need is already computed — never restructure the existing control flow of a passing stage.
- If the new stage should be traced, add the corresponding `self.trace_recorder.record_stage(...)`/`record_guardrail(...)` call following the existing pattern (see `observability.md`) — but the trace recorder itself must never be required for the pipeline to function (it defaults to a no-op).
- Update `apps/api/tests/test_rag_orchestrator.py` and re-run the full suite; this file is the primary regression guard for the entire pipeline.
