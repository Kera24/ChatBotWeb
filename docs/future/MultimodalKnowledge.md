# Multimodal Knowledge

## Purpose

Extend knowledge ingestion beyond plain text to images, structured tables, and audio transcripts, so assistants can answer questions grounded in non-text source material.

## Current limitation

`docs/architecture/knowledge-ingestion.md`'s extraction step produces plain text only; documents with meaningful image or table content lose that information at extraction time.

## Why postponed

Text-only ingestion needed to be proven reliable first (evaluation framework, chunking, embeddings all assume text); multimodal support is a genuinely new extraction/embedding surface, not an incremental change to the existing one.

## Dependencies

- A multimodal-capable embedding/generation provider (none exists yet — only `MockAIProvider`, `docs/architecture/retrieval.md`).
- Extraction-quality signal (`docs/engineering/document-processing.md`'s future item) to know which documents need multimodal handling vs. text-only extraction.

## Implementation phases

1. OCR/table-extraction as a text-normalization step first (convert image/table content to text, no new storage model) — lowest-risk increment.
2. Native multimodal embeddings (image embeddings alongside text embeddings) once a provider supports it, as a genuinely new retrieval type.
3. Audio transcript ingestion via a transcription step feeding the existing text pipeline.

## Technical design

Phase 1 stays inside the existing `DocumentVersion`/`Chunk` model (extracted content is still text, just extracted differently). Later phases require schema additions (e.g. a `Chunk.modality` field, modality-aware retrieval ranking) — scoped separately when reached.

## Evaluation plan

New evaluation cases specifically targeting multimodal-sourced content; compare answer grounding quality against text-only baseline for the same source documents pre/post multimodal extraction.

## Rollback strategy

Phase 1 (OCR/table-to-text) is additive and reversible per-document (re-run text-only extraction). Later native-multimodal phases should ship behind a flag before being tenant-default.

## Success metrics

Documents previously unusable (image-heavy PDFs, scanned documents) become answerable with grounded citations, without degrading text-only document performance.
