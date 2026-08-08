# SOP: Adding Rerankers

## Purpose

Add a second-pass reranking step over initial retrieval candidates, per `docs/future/Reranking.md`.

## When to use

Only after `docs/future/HybridRetrieval.md` has shipped — reranking operates on the fused candidate pool, not vector-only results.

## Step-by-step process

1. Implement the reranking step after initial candidate retrieval, before citation policy (Layer F) and evidence sufficiency (Layer A+B) — reranking narrows/reorders, it never bypasses guardrails.
2. A/B against non-reranked retrieval on the evaluation case set, measuring both quality and added latency.
3. If latency cost is too high to apply universally, make reranking conditional (only invoked when initial candidate confidence is low).
4. Flag-gate the rollout, per-tenant validated before default.

## Validation

`docs/checklists/retrieval-checklist.md`, `docs/checklists/performance-checklist.md` (latency cost is a first-class concern here).

## Rollback

Flag flip to disable; reverts to single-pass ranking with no schema or data changes.

## Success criteria

Measurable precision@k or grader-scored answer-quality improvement that justifies the added latency, validated per-tenant before being made default.
