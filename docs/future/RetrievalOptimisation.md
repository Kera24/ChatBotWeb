# Retrieval Optimisation

## Purpose

Umbrella improvement track for retrieval quality beyond the individually-specced items (hybrid retrieval, reranking, query rewrite) — chunking strategy, similarity-threshold tuning, and retrieval-count tuning.

## Current limitation

Chunking is fixed-size word-count (`docs/engineering/chunking.md`); retrieval `top_k`/similarity thresholds are static configuration, not tuned against evaluation data.

## Why postponed

Needs the same observability + evaluation foundation as the other retrieval-quality items; tuning parameters without a measurement harness risks local, unverified improvements that don't generalize.

## Dependencies

- `docs/architecture/evaluation.md`'s case set must be large/varied enough to detect the effect of parameter changes.
- Observability retrieval traces (`ai_retrieval_traces`, `docs/architecture/observability.md`) to see actual selected-vs-rejected chunk patterns in production.

## Implementation phases

1. Semantic/structure-aware chunking (headings, sentence boundaries) instead of fixed word count.
2. Systematic similarity-threshold and `top_k` tuning against the evaluation case set.
3. Per-document-type chunking strategy once enough document-type diversity exists in production tenants.

## Technical design

Changes land inside `app.services.chunking` and `app.services.retrieval_context` as tunable, evaluated parameter changes — not a new pipeline stage.

## Evaluation plan

Each tuning change evaluated independently against the full evaluation gate before being adopted as a new default; no bundling of multiple untested changes into one release.

## Rollback strategy

Chunking changes require re-chunking existing documents to take effect for old content — old chunks remain valid until a document is re-processed, so rollback is "stop applying the new default to new ingestion," not a live migration.

## Success metrics

Measurable retrieval precision/recall and grader-score improvement on the evaluation case set, tracked per parameter change.
