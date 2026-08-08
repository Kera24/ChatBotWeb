# RAG Pipeline Checklist

## Required validation

- `npm run api:test`, focused on `test_rag_orchestrator.py` (the primary regression guard for the whole pipeline) plus the full suite.
- `npm run eval:test` — any pipeline change must be evaluated, not just unit-tested.

## Things to verify

- Both the authenticated (`workspaces.py`) and public-widget (`rag_adapter.py`) paths still call the same `RAGOrchestrator.answer()` — no per-channel fork.
- New stages are additive, inserted after the value they need is already computed — never restructure a passing stage's control flow (`docs/architecture/retrieval.md`).
- Knowledge-scope isolation preserved: `document_ids=None` (no assistant resolved) vs. `document_ids=[]` (assistant resolved, empty scope → zero chunks) distinction is not collapsed.
- Fallback semantics preserved: any guardrail block or empty retrieval routes through `_persist_fallback()` with `answer_state="fallback"` and a `guardrail_reason_code` — never a silent drop.
- If traced, the new stage calls `self.trace_recorder.record_stage(...)`/`record_guardrail(...)` following the existing pattern, and the trace recorder itself stays optional (defaults to no-op).

## Common mistakes

- Forking pipeline logic per channel "just this once."
- Collapsing the `None` vs `[]` knowledge-scope distinction.
- Making the trace recorder a hard dependency instead of defaulting to no-op.
- Skipping the evaluation-gate run because "it's just a small pipeline tweak."

## Required documentation

- Update `docs/architecture/retrieval.md`/`docs/engineering/rag-pipeline.md` if pipeline stage order or semantics change.
- New guardrail layers additionally update `docs/architecture/guardrails.md`.

## Definition of Done

`test_rag_orchestrator.py` and the full `api:test` suite pass; evaluation gate passes with no threshold changes; both authenticated and public paths verified; knowledge-scope isolation behavior explicitly tested.
