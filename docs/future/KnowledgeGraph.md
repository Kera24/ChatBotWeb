# Knowledge Graph

## Purpose

Represent relationships between entities/facts across documents (not just similarity between text chunks), to support questions that require connecting information across multiple sources.

## Current limitation

Retrieval (`docs/architecture/retrieval.md`) treats each chunk independently; there is no structured representation of how entities/facts relate across a tenant's knowledge base, so multi-hop questions ("how does X relate to Y") depend entirely on both facts co-occurring in retrieved chunks.

## Why postponed

Highest-complexity, highest-uncertainty item in the retrieval roadmap; requires hybrid retrieval, reranking, and a mature evaluation framework to even measure whether a knowledge graph improves answers, none of which should be skipped to get here first.

## Dependencies

- `docs/future/HybridRetrieval.md` and `docs/future/Reranking.md` (graph-augmented retrieval is a further step beyond these, not a replacement for them).
- Production evidence of specific multi-hop-question failure patterns from observability traces (`docs/architecture/observability.md`).

## Implementation phases

1. Entity extraction from ingested documents (NER-style) as an additive metadata layer — no schema change to core retrieval yet.
2. Relationship extraction between entities within and across documents; store as a graph structure (new tables or a graph-capable store, TBD at design time).
3. Graph-augmented retrieval: use graph traversal to expand/re-rank candidate chunks for multi-hop questions specifically (not all questions).
4. Evaluate against a case set specifically constructed for multi-hop questions.

## Technical design

Deliberately unspecified beyond phase 1 — this is the least mature item in the roadmap and its technical design should be finalized only once `docs/future/HybridRetrieval.md` and `docs/future/Reranking.md` are shipped and their own limitations are understood.

## Evaluation plan

A dedicated multi-hop-question evaluation case set, since standard single-fact evaluation cases won't reveal a knowledge graph's benefit.

## Rollback strategy

Purely additive (graph data supplements, doesn't replace, chunk-based retrieval) — disabling graph-augmented retrieval reverts to the standard pipeline with no data loss.

## Success metrics

Measurable improvement in multi-hop-question answer quality/groundedness, with no regression on single-fact questions.
