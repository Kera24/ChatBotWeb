# SOP: Adding Hybrid Retrieval

## Purpose

Combine vector and lexical (keyword/BM25) search, per `docs/future/HybridRetrieval.md`.

## When to use

Once observability data shows exact-term queries underperforming under vector-only retrieval.

## Step-by-step process

1. Add a Postgres full-text (`tsvector`) index alongside the existing pgvector index on `Chunk`.
2. Implement a fusion ranking (e.g. reciprocal rank fusion) combining vector and lexical scores in a new `app.services.lexical_search` module mirroring `vector_search`'s interface.
3. `assemble_retrieval_context()` calls both and fuses results before citation/evidence-sufficiency guardrail layers run — guardrail logic itself is unchanged.
4. A/B the fused ranking against vector-only on a case set specifically constructed with exact-term-dependent questions.
5. Roll out behind a per-workspace flag, monitored via observability.

## Validation

`docs/checklists/retrieval-checklist.md`; retrieval precision/recall and downstream grader scores compared vector-only vs. hybrid.

## Rollback

Per-workspace flag defaults to vector-only; disabling reverts with no schema rollback needed (the full-text index is additive).

## Success criteria

Reduced evidence-insufficient/fallback rate specifically on exact-term queries; no regression in overall evaluation gate scores.
