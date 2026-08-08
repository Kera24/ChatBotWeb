# Document Processing — Current / Future / Out of Scope

## Current

Extraction is automated on upload, with a manual fallback (`app.services.manual_extraction.manually_extract_document_version()`) for content that can't be auto-extracted. See `docs/architecture/knowledge-ingestion.md`'s "Processing pipeline" step 2 for the full flow and RBAC.

## Future

- OCR / image-based document extraction, and structured-table extraction — see `docs/future/MultimodalKnowledge.md`.
- Automatic extraction-quality scoring to flag documents that likely need the manual-extraction fallback, instead of relying on manual review.

## Out of scope (not planned)

- Editing extracted text in place after a version is `ready` — corrections go through a new document version, not a patch to history, to keep evaluation and citation provenance stable.
