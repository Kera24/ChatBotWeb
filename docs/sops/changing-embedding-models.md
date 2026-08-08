# SOP: Changing Embedding Models

## Purpose

Change the active embedding provider/model/dimension safely, given that query and chunk vectors must always come from the same model to be comparable.

## When to use

Following `docs/future/EmbeddingBakeoff.md`'s comparison process, or when a chosen embedding provider needs to be upgraded/replaced.

## Step-by-step process

1. Follow the Embedding Models workflow in `docs/workflows/ai-development.md`.
2. Never reinterpret existing vectors in place — a dimension or model change requires full re-embedding.
3. Dual-write phase: embed new documents with both old and new models behind a flag; compare retrieval quality on a shadow path.
4. Once shadow comparison shows parity/improvement, re-embed existing corpus (batched, tenant-by-tenant or globally depending on scale).
5. Cut query-time embedding over to the new model only after the full corpus is re-embedded (mixed old/new vectors in one similarity search is invalid).
6. Decommission old vectors after a safe retention window.

## Validation

Retrieval precision/recall comparison against the evaluation case set (`docs/checklists/retrieval-checklist.md`, `docs/checklists/evaluation-checklist.md`).

## Rollback

Keep old vectors until the new model is fully validated in production; rollback is reverting `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION` config and re-serving from the retained old vectors.

## Success criteria

No mixed-model similarity search ever occurs; retrieval quality parity or improvement confirmed before old vectors are decommissioned.
