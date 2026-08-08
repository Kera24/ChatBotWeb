# SOP: Adding New Data Sources

## Purpose

Support a new category of source content (beyond text documents — e.g. multimodal per `docs/future/MultimodalKnowledge.md`, or a new connector-fed source type).

## When to use

A tenant need exists for a source type the current pipeline can't ingest (images, tables, audio, or a new connector's native content shape).

## Step-by-step process

1. Determine whether this is a connector question (`docs/sops/adding-connectors.md`) or an extraction/format question (`docs/future/MultimodalKnowledge.md`).
2. Phase 1: normalize the new source to text via an extraction step, staying inside the existing `DocumentVersion`/`Chunk` model — lowest-risk increment.
3. Phase 2 (only if needed): native handling (e.g. image embeddings) as a genuinely new retrieval type, requiring schema additions — scoped as its own effort.
4. Add evaluation cases specifically targeting the new source type.

## Validation

`docs/checklists/rag-checklist.md`; compare answer grounding quality against text-only baseline for the same underlying content.

## Rollback

Phase 1 is additive and reversible per-document (re-run text-only extraction). Later native-handling phases should ship behind a flag before being tenant-default.

## Success criteria

Previously unusable source content becomes answerable with grounded citations, without degrading existing source-type performance.
