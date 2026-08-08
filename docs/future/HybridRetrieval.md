# Hybrid Retrieval

## Purpose

Combine vector similarity search (current) with keyword/lexical search (e.g. BM25/Postgres full-text) so retrieval catches exact-term matches (product codes, proper nouns, error codes) that pure embedding similarity sometimes ranks poorly.

## Current limitation

`app.services.vector_search` (`docs/architecture/vector-storage.md`) is vector-only. A query containing an exact SKU, error code, or rare proper noun can retrieve semantically-similar-but-wrong chunks ahead of the chunk that contains the literal term.

## Why postponed

No production evidence yet that this is a measured retrieval-quality problem for real tenant corpora; `docs/adr/0024-observability-before-scaling.md` established that scaling/quality investment should follow observability data, not assumption. Building hybrid ranking logic before there's a case set that demonstrates the gap risks tuning against a hypothetical.

## Dependencies

- AI observability trace data (`docs/architecture/observability.md`) to identify real queries where vector-only retrieval underperformed.
- A stable evaluation case set (`docs/architecture/evaluation.md`) large and varied enough to measure a ranking-strategy change without noise.

## Implementation phases

1. Instrument retrieval traces to flag low-similarity-but-selected chunks as candidates for lexical-miss analysis.
2. Add a Postgres full-text (`tsvector`) index alongside the existing pgvector index on `Chunk`.
3. Implement a fusion ranking (e.g. reciprocal rank fusion) combining vector and lexical scores.
4. A/B the fused ranking against vector-only on the evaluation case set before enabling for any tenant.
5. Gradual rollout behind a per-workspace flag, monitored via observability traces.

## Technical design

New `app.services.lexical_search` module mirroring `vector_search`'s interface; `assemble_retrieval_context()` (`docs/architecture/retrieval.md`) calls both and fuses results before the existing citation/evidence-sufficiency guardrail layers run — guardrail logic itself does not change.

## Evaluation plan

Compare retrieval precision/recall and downstream grader scores (`docs/engineering/graders.md`) between vector-only and hybrid on a case set specifically constructed to include exact-term-dependent questions.

## Rollback strategy

Per-workspace flag defaults to vector-only; disabling the flag reverts to the current single-path retrieval with no schema rollback needed (the full-text index is additive).

## Success metrics

Reduced evidence-insufficient/fallback rate (`docs/architecture/observability.md`'s metrics) specifically on exact-term queries, with no regression in overall evaluation gate scores.
