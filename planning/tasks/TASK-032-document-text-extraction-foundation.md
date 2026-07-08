# Task: Document Text Extraction Foundation

## Task ID

TASK-032

## Linked epic/story

- EPIC-003

## Objective

Add a service-layer text extraction foundation for supported MVP document types.

This task creates callable extraction utilities and tests only. It does not connect extraction to uploads automatically and does not add processing queues, chunking, embeddings, vector search, RAG, widget, or analytics behaviour.

## Scope

Implement only:

- Text extraction service foundation for TXT files.
- Text extraction service foundation for CSV files.
- Text extraction service foundation for PDF files.
- Text extraction service foundation for DOCX files.
- Extraction result object and structured safe extraction errors.
- File path safety checks for extraction inputs.
- Tests using small sample files.
- Minimal parser dependencies required for PDF and DOCX.
- Sprint pointer update to TASK-032.

## Out of scope

Do not implement:

- Processing queue.
- Automatic extraction on upload.
- Chunking.
- Embeddings.
- Vector search.
- RAG runtime.
- Widget behaviour.
- Analytics.

## Requirements

- Extraction remains callable from the service layer only.
- Extraction callers provide trusted file paths and source types from stored metadata, not uploaded filenames.
- Extraction can be constrained to a storage root and rejects paths outside that root.
- Extraction failures return structured errors instead of raising parser exceptions to API callers.
- Supported extraction types are `txt`, `csv`, `pdf`, and `docx`.
- Dependencies remain minimal and justified.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-032-document-text-extraction-foundation.md` exists.
- Text extraction service exists for TXT, CSV, PDF, and DOCX.
- Extraction result and error structures exist.
- Tests cover successful extraction for all supported types.
- Tests cover structured failure behaviour.
- Tests cover file safety behaviour.
- `.ai/CURRENT_SPRINT.md` lists TASK-032 as current task.
- Required validation commands have been run and reported.
