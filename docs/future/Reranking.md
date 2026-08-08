# Reranking

## Purpose

Add a second-pass reranking step (cross-encoder or LLM-based) over initially-retrieved candidates to improve final chunk selection precision beyond single-pass vector/hybrid similarity ranking.

## Current limitation

`assemble_retrieval_context()` (`docs/architecture/retrieval.md`) selects chunks from a single similarity-ranked pass; there is no second-stage re-scoring of the top candidates.

## Why postponed

Adds real latency (a reranking model call per request) and needs `docs/future/HybridRetrieval.md`'s candidate set to be in place first — reranking only helps if the initial candidate pool is already reasonably good.

## Dependencies

- `docs/future/HybridRetrieval.md` (reranking operates on the fused candidate pool, not vector-only results).
- A real (non-mock) provider capable of cheap reranking calls, or a dedicated lightweight cross-encoder model.

## Implementation phases

1. Add a reranking step after initial candidate retrieval, before citation/evidence-sufficiency guardrails — reranking narrows/reorders candidates, it doesn't bypass guardrails.
2. A/B against non-reranked retrieval on the evaluation case set, measuring both quality and added latency.
3. Make reranking conditional (only invoked when initial candidate confidence is low) if latency cost proves too high to apply universally.

## Technical design

New `app.services.reranking` module invoked from `assemble_retrieval_context()`; guardrail layers F (citation policy) and A+B (evidence sufficiency) run unchanged, against the reranked output.

## Evaluation plan

Precision@k improvement and grader-scored answer quality vs. added p95 latency, on the standard evaluation case set plus any hybrid-retrieval-specific cases.

## Rollback strategy

Flag-gated; disabling reverts to single-pass ranking with no schema or data changes.

## Success metrics

Measurable answer-quality improvement that justifies the added latency, validated per-tenant before being made default.
