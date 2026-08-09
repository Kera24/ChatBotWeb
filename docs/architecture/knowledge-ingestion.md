# Knowledge Ingestion Architecture

Documents flow: upload → extract → chunk → embed → active version. Every step transitions through explicit lifecycle states so processing failures are visible and recoverable, not silent.

## Data model

- `Document` (`app.db.models.document`) — `status` (default `uploaded`), `visibility` (default `workspace`), `source_type`/`source_key`, `active_document_version_id`, soft-delete/archival fields (`archived_at`, `expires_at`, `deleted_at`).
- `DocumentVersion` (`app.db.models.document_version`) — `processing_status` (default `pending`), `checksum` (unique per document+checksum, dedupes re-uploads), `original_file_path`/`extracted_text_path`, `processing_error`.
- `Chunk` (`app.db.models.chunk`) — see `vector-storage.md`.

## Lifecycle transitions

Centralized in `app.services.document_lifecycle` (`transition_document_status`, `transition_document_version_status`), with an explicit `allowed_transitions` map — invalid transitions raise `InvalidLifecycleTransition` rather than silently succeeding. `"archived"`/`"expired"` are special-cased. Every transition writes an audit event. **Do not mutate `Document.status`/`DocumentVersion.processing_status` directly anywhere** — always go through this module, even for a one-off script.

## Processing pipeline

Orchestrated from `app.api.v1.documents`:

1. **Upload** — `create_uploaded_document_with_version()` via `LocalDocumentStorage`; size/type validated (`UnsupportedUploadType`, `UploadTooLarge`).
2. **Extraction** — automated via the upload pipeline, or `app.services.manual_extraction.manually_extract_document_version()` for content that needs manual text entry instead (e.g. content that can't be auto-extracted).
3. **Chunking** — `app.services.chunking.chunk_document_version()`. Size controlled by `CHUNK_SIZE_WORDS`/`CHUNK_OVERLAP_WORDS` in `Settings`. Strategy selectable via `settings.CHUNKING_STRATEGY` (default `structure_aware` per ADR-0031; `fixed_word` — the original, unchanged code path — remains available as a one-line rollback; `structure_semantic` is opt-in — see `docs/engineering/chunking.md`).
4. **Embedding** — `app.services.embeddings.embed_document_version_chunks()`, via whichever provider `build_embedding_provider()` constructs from `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION`. See `vector-storage.md` for provider details and the Postgres-only vector-write behavior.
5. **Activation** — `Document.active_document_version_id` is updated once a version is `ready`; only the active version's chunks are retrievable.

## RBAC

`org_owner`/`client_admin`/`viewer` can read (`DocumentViewerDependency`); `org_owner`/`client_admin` can upload/manage (`DocumentManagerDependency`).

## Frontend

`apps/web/app/knowledge/page.tsx` → `components/knowledge/knowledge-base-client.tsx` — a single client component driving upload, listing, and status display.

## Rules

- Never bypass `document_lifecycle`'s transition map.
- Never write `Chunk.embedding_vector` outside `embed_document_version_chunks()` — see `vector-storage.md` for why the write path is dialect-conditional.
- A re-upload of identical content should dedupe via the `checksum` unique constraint, not create a duplicate version — if you touch upload logic, verify this still holds.
