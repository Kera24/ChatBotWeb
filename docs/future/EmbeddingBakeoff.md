# Embedding Bake-off

## Purpose

Systematically compare retrieval quality across multiple embedding providers/models before committing to one at scale, rather than keeping the current single-provider default indefinitely by inertia.

## Current limitation

`EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION` (`docs/architecture/knowledge-ingestion.md`) is a single fixed configuration; no comparative evaluation across providers has been run.

## Why postponed

No live (non-mock) generation provider exists yet either (`docs/architecture/retrieval.md`'s "Providers" section) — prioritizing a real generation provider and production-scale evaluation data ahead of an embedding comparison that would otherwise be run on synthetic/mock-era data.

## Dependencies

- A stable, representative evaluation case set with real (not mock) provider responses.
- `docs/architecture/observability.md`'s cost tracking, since embedding choice has direct cost implications (`docs/future/CostOptimisation.md`).

## Implementation phases

1. Define a fixed comparison harness: same document corpus, same chunking, multiple embedding providers, same retrieval evaluation case set.
2. Run each candidate provider through the harness, capturing recall/precision and cost-per-embedding.
3. Recommend a default based on the results; document the decision as a new ADR either confirming the current default or changing it.
4. If changing, plan a re-embedding migration for existing tenant corpora (re-embed is required — dimension/model changes aren't compatible in place).

## Technical design

A standalone offline evaluation script/harness (not a runtime feature) that calls `build_embedding_provider()` with different configs against the same corpus and scores retrieval quality via the existing evaluation framework.

## Evaluation plan

Recall@k and grader-scored answer quality (`docs/engineering/graders.md`) per candidate provider, plus cost-per-million-tokens comparison.

## Rollback strategy

Not applicable in the traditional sense — this is a comparison exercise, not a deployed feature. If a provider switch results from it, that switch follows the same re-embedding migration rollback plan as any embedding config change (keep old embeddings until new ones are verified).

## Success metrics

A documented, evidence-based embedding provider recommendation (ADR), whether or not it changes the current default.
