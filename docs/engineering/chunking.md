# Chunking — Current / Future / Out of Scope

## Current

Fixed-size word-count chunking with overlap, via `app.services.chunking.chunk_document_version()`, size controlled by `CHUNK_SIZE_WORDS`/`CHUNK_OVERLAP_WORDS` (`Settings`). See `docs/architecture/knowledge-ingestion.md`'s "Processing pipeline" step 3.

## Future

- Semantic/structure-aware chunking (headings, tables, sentence boundaries) instead of fixed word count — see `docs/future/RetrievalOptimisation.md`.
- Per-document-type chunking strategy (e.g. FAQ pairs chunked differently from long-form prose).

## Out of scope (not planned)

- Query-time dynamic re-chunking — chunking stays a fixed ingestion-time step; changing it means re-processing the document version, not adapting per query.
