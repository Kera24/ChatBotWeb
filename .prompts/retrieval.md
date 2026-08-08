# Prompt Template: Retrieval / RAG

Use this when the task touches the RAG pipeline, embeddings, vector search, or prompt assembly.

## Scope

`apps/api/app/ai/rag_orchestrator.py`, `apps/api/app/ai/service.py`, `apps/api/app/services/{retrieval_context,vector_search,embeddings,prompt_assembly}.py`, `apps/api/app/ai/providers/*`, `apps/api/app/ai/model_registry.py`. See `docs/architecture/retrieval.md` and `docs/architecture/vector-storage.md`.

## Constraints

- `RAGOrchestrator.answer()` is the single entry point for both the authenticated and public-widget paths — never fork logic per channel.
- Preserve the `document_ids=None` (no scope restriction) vs. `document_ids=[]` (explicit empty scope → zero results) distinction exactly — this is a tenant-isolation-adjacent security boundary, not a convenience default.
- New pipeline stages/checks are additive, placed after the value they need is already computed — never restructure existing stage control flow.
- SQLite and Postgres have genuinely different vector-search code paths (`vector-storage.md`) — a change to search ranking needs verification against both, not just whichever the test suite happens to run against locally.
- Cost/token accounting must never silently treat unknown pricing as `$0` — check `pricing_known`/nullable cost fields.
- Only `MockAIProvider` exists today — don't assume a real provider's behavior (streaming, function calling, etc.) without checking `docs/architecture/retrieval.md`'s current-state section first.

## Validation

`npm run api:test` (full suite — `test_rag_orchestrator.py`) and `npm run eval:test`.

## Reporting

Full Report if the pipeline's stage order, guardrail wiring, or retrieval-scoping logic changed; Short Report for a narrow provider/config addition.

## Expected output

Changes to the relevant `app/ai/*`/`app/services/*` files, with `test_rag_orchestrator.py` extended or confirmed unaffected, and evaluation results reported if run.

## What NOT to modify

- The knowledge-scope `None` vs `[]` semantics.
- Guardrail wiring (see `.prompts/guardrails.md` if the task is actually about a guardrail).
- Evaluation thresholds (see `.prompts/evaluation.md` if scores shift).
