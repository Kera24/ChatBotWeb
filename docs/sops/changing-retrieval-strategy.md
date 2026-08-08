# SOP: Changing Retrieval Strategy

## Purpose

Change chunking, ranking, or candidate-selection logic in retrieval without regressing answer quality or breaking knowledge-scope isolation.

## When to use

Implementing any item from the retrieval-quality track: `docs/future/RetrievalOptimisation.md`, `docs/future/HybridRetrieval.md`, `docs/future/Reranking.md`, `docs/future/QueryRewrite.md`.

## Step-by-step process

1. Follow the Retrieval workflow in `docs/workflows/ai-development.md`.
2. Implement the change behind a flag; verify knowledge-scope isolation (`None` vs `[]` distinction) is unaffected.
3. Run precision/recall comparison against the evaluation case set.
4. Shadow-compare (compute new ranking, serve old, log divergence) before serving live.
5. Roll out per-workspace, monitored via `ai_retrieval_traces`.

## Validation

`docs/checklists/retrieval-checklist.md` in full.

## Rollback

Flag flip back to the prior ranking logic; no schema/data impact for ranking-only changes (chunking changes require re-processing to fully revert, since old chunks persist until a document is re-chunked).

## Success criteria

Precision/recall improvement or parity on the evaluation case set; guardrail layers (citation policy, evidence sufficiency) confirmed still firing correctly against the new retrieval output.
