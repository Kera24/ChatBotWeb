# Skill: RAG Pipeline

## Purpose

Implement or modify the retrieval-augmented-generation pipeline: `RAGOrchestrator`, providers, prompt assembly, or how stages are wired together.

## When to use

Any task touching `app.ai.rag_orchestrator`, `app.ai.service`, `app.ai.providers.*`, `app.ai.model_registry`, or the retrieval/prompt-assembly services it calls. For a specific guardrail layer's own logic, prefer the `guardrails` skill (still read this one for pipeline context). For vector-search/embedding internals specifically, the `retrieval` skill overlaps — this skill is the orchestrator-level view, `retrieval` is the vector-search-level view.

## Architecture assumptions

`RAGOrchestrator.answer()` is the single entry point for both authenticated and public-widget requests. Stage order and guardrail layer taxonomy are fixed (see `docs/architecture/retrieval.md`, `docs/architecture/guardrails.md`) — read both in full before changing pipeline structure. Only `MockAIProvider` exists today.

## Files typically modified

- `apps/api/app/ai/rag_orchestrator.py`
- `apps/api/app/ai/service.py`
- `apps/api/app/ai/providers/*.py`
- `apps/api/app/ai/model_registry.py`
- `apps/api/app/services/{retrieval_context,vector_search,embeddings,prompt_assembly}.py`
- `apps/api/tests/test_rag_orchestrator.py`

## Files never modified

- Guardrail module internals (use the `guardrails` skill for that half of a combined task).
- `app/evaluation/policy.py`/`gate.py` (evaluation thresholds).
- Anything under `app/observability/` beyond adding the standard trace-recording call for a new stage (that's additive, not a redesign).

## Validation commands

```
npm run api:test
npm run eval:test
```

## Expected report format

Full Report — pipeline changes are architecturally significant by nature. Include: what stage order changed (if any), what the full test suite result was, and what the evaluation run's pass/fail counts were before/after if evaluation was run.

## Common pitfalls

- Forking behavior between the authenticated and public-widget paths — they must share one `RAGOrchestrator.answer()` call.
- Breaking the `document_ids=None` vs. `document_ids=[]` distinction when touching knowledge-scope resolution.
- Assuming SQLite test-passing proves the Postgres vector-search path is correct (`docs/architecture/vector-storage.md`) — they're genuinely different implementations.
- Silently treating unknown model pricing as `$0` instead of leaving cost fields null/`pricing_known=False`.
- Restructuring existing stage control flow instead of adding a new stage additively after an existing decision point.

## Best practices

- Read `docs/architecture/retrieval.md`'s full stage list before touching anything — know exactly where your change fits.
- Extend `RAGOrchestrationRequest`/`RAGOrchestrationResult`/`RAGOrchestratorDependencies` with new trailing optional fields rather than changing existing ones — there are exactly 3 production call sites plus the test file that all construct these via keyword args; trailing-optional-field additions are safe, anything else needs every call site checked.
- Run `test_rag_orchestrator.py` before and after your change and compare pass counts, not just "still green."
