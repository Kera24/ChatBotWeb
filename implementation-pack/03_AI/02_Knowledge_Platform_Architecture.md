# Knowledge Platform Architecture

## 1. Purpose

The knowledge platform is the tenant-isolated foundation for storing, processing, retrieving, and citing client knowledge in ChatBotWeb / Yoranix AI Platform.

Its purpose is to let each organisation and workspace manage trusted knowledge sources that can be converted into searchable chunks and used by RAG chatbots to produce grounded answers with citations.

The MVP knowledge platform must support:

- Client-admin uploaded files.
- Manually created FAQ knowledge.
- Asynchronous ingestion and processing.
- Tenant-aware retrieval from active knowledge only.
- Source traceability from answer to citation, chunk, document version, and document.

The platform must be designed as a long-term knowledge layer, not a one-off upload feature. Future source connectors must fit the same document, version, chunk, embedding, citation, and chat answer model.

## 2. Document Source Types

### MVP source types

- `pdf`: uploaded PDF documents.
- `docx`: uploaded Microsoft Word documents.
- `txt`: uploaded plain text documents.
- `csv`: uploaded tabular text data.
- `faq`: manually created question-and-answer content.

### Future source types

- `url_future`: a single imported URL or manually submitted webpage.
- `web_crawler_future`: a crawler-managed set of pages from an allowed domain.
- `sharepoint_future`: documents synced from Microsoft SharePoint.
- `onedrive_future`: documents synced from Microsoft OneDrive.
- `google_drive_future`: documents synced from Google Drive.
- `integration_future`: reserved source type for future third-party systems.

Future source types must map into the same core model:

```text
external source -> document -> document_version -> chunks -> embeddings -> retrieval -> citations -> chat answer
```

External integrations may add connector metadata and sync jobs later, but retrieval and citation semantics must not depend on source-specific tables.

## 3. Document Lifecycle

Documents represent stable knowledge source identities within a workspace. Document versions represent immutable snapshots of a document source at a point in time.

### Lifecycle stages

1. `created`: a document record is created for an uploaded file, FAQ, or future external source.
2. `uploaded`: source content is stored in tenant-scoped object storage or captured as structured FAQ content.
3. `queued`: a processable document version is queued for ingestion.
4. `processing`: text extraction, normalization, chunking, and embedding work is running.
5. `ready`: the latest effective version has ready chunks that can be retrieved.
6. `failed`: processing failed and the document version is not retrievable.
7. `replaced`: a newer version supersedes a previous effective version.
8. `archived`: the document is intentionally removed from retrieval but retained for audit/history.
9. `expired`: the document or version passed its configured `expires_at` value and is excluded from retrieval.
10. `deleted`: the document is soft-deleted and excluded from all normal lists, retrieval, and citations for new answers.

### Lifecycle rules

- A document may have many versions, but only one version should be current and effective for retrieval at a time.
- A failed version must not make the previous ready version unavailable unless the document itself is archived, expired, or deleted.
- Archiving a document excludes all versions and chunks from retrieval.
- Expiry excludes the document or version from retrieval without destroying historical metadata.
- Deletion should be soft-delete first; physical deletion from object storage can be handled by a future retention task.

## 4. Versioning Model

### Documents

`documents` store the durable identity, tenant context, high-level status, and source classification for a knowledge source.

Required conceptual fields:

- `id`
- `organisation_id`
- `workspace_id`
- `title`
- `source_type`
- `status`
- `category`
- `visibility`
- `created_by_user_id`
- `created_at`
- `updated_at`
- `archived_at`
- `deleted_at`

### Document versions

`document_versions` store immutable processable snapshots.

Required conceptual fields:

- `id`
- `document_id`
- `version_number`
- `source_uri`
- `original_file_path`
- `extracted_text_path`
- `checksum`
- `source_last_modified_at`
- `processing_status`
- `processing_error`
- `effective_from`
- `expires_at`
- `created_at`
- `created_by_user_id`

### Versioning rules

- Version numbers increment per document.
- Version content should be immutable after processing starts.
- Re-uploading or resyncing a changed source creates a new version.
- If checksum has not changed, future ingestion may skip creating a new processable version.
- Only versions with ready processing status and valid effective/expiry dates can provide retrievable chunks.
- Citations should preserve the version used at answer time even if the document later changes.

## 5. Ingestion Pipeline

The ingestion pipeline turns a source into retrieval-ready chunks and embeddings.

### Pipeline steps

1. Resolve tenant context: validate `organisation_id`, `workspace_id`, actor, role, and source ownership.
2. Store source: save file or source payload to tenant-scoped storage.
3. Create version: create immutable `document_versions` row with checksum and source metadata.
4. Queue job: enqueue processing using the document version ID.
5. Validate source: check file type, size, checksum, and safe filename/source metadata.
6. Extract text: parse source content into normalized plain text and structural metadata.
7. Persist extracted text: store extracted text in tenant-scoped storage where appropriate.
8. Chunk content: split text into ordered chunks with token counts and source location metadata.
9. Create chunk records: write chunks with tenant IDs, document ID, version ID, index, status, and metadata.
10. Generate embeddings: call the embedding abstraction for each retrievable chunk.
11. Store embeddings: store vectors in pgvector first, attached to chunk records or a future embeddings table.
12. Mark ready: mark chunks, version, and document ready only after all required processing succeeds.
13. Audit and metrics: record administrative actions, processing latency, token usage, and failure signals when available.

### Pipeline design rules

- Long-running processing must run asynchronously.
- Jobs must be idempotent for a given document version.
- Partial processing must not expose chunks to retrieval until the version is ready.
- Uploaded documents and extracted text are untrusted input.
- Prompt-injection-like content in source documents must be treated as content, not instructions.

## 6. Processing States

### Document status

- `uploaded`: source exists but no ready version is available yet.
- `processing`: at least one current version is being processed.
- `ready`: current effective version has ready retrievable chunks.
- `failed`: current processing attempt failed and no ready current version is available.
- `archived`: excluded from retrieval by admin action.
- `expired`: excluded from retrieval by date policy.
- `deleted`: soft-deleted and excluded from normal use.

### Document version processing status

- `pending`: version created but not queued.
- `queued`: processing job is waiting.
- `extracting`: text extraction is running.
- `chunking`: chunk generation is running.
- `embedding`: embedding generation is running.
- `ready`: all chunks and embeddings required for retrieval are ready.
- `failed`: processing stopped due to a non-recoverable or exhausted retry failure.
- `superseded`: version was replaced by a newer effective version.

### Chunk status

- `pending`: chunk record exists but is not retrievable.
- `embedding`: embedding generation is pending or running.
- `ready`: chunk has retrievable text and vector data.
- `failed`: chunk processing failed.
- `excluded`: chunk should not be retrieved because of policy, visibility, expiry, or source state.

### Embedding state

For MVP, embeddings may be stored directly on `chunks.embedding_vector`. If a future `embeddings` table is introduced, it should use equivalent states:

- `pending`
- `ready`
- `failed`
- `stale`

## 7. Retry and Failure Model

### Retryable failures

- Temporary object storage read errors.
- Temporary queue or worker errors.
- Embedding provider rate limits or timeouts.
- Transient database connection errors.

Retryable failures should use bounded retries with backoff and should preserve job idempotency.

### Non-retryable failures

- Unsupported file type.
- File exceeds allowed size.
- Corrupt or encrypted file that cannot be parsed.
- Empty extracted text after successful parsing.
- Tenant context mismatch.
- Source no longer exists or actor no longer has permission.

Non-retryable failures should mark the document version as `failed`, store a safe `processing_error`, and keep the document excluded from retrieval unless an older ready version remains effective.

### Failure handling rules

- Never expose stack traces, provider secrets, storage paths, or internal prompts to users.
- Store operational diagnostics separately from user-safe error messages where needed.
- Failed chunks and failed versions must be excluded from retrieval.
- Retrying a failed version may reuse the same version only if the source snapshot is unchanged.
- Uploading changed content after a failed version creates a new version.

## 8. Metadata Model

Metadata must support retrieval quality, citations, analytics, filtering, and future integrations without weakening tenant isolation.

### Document metadata

- `title`
- `source_type`
- `category`
- `language`
- `visibility`
- `source_display_name`
- `external_source_id` for future connectors
- `external_source_url` for future connectors and URL sources
- `created_by_user_id`
- `archived_at`
- `deleted_at`

### Version metadata

- `version_number`
- `checksum`
- `source_uri`
- `original_file_path`
- `extracted_text_path`
- `source_last_modified_at`
- `effective_from`
- `expires_at`
- `processing_status`
- `processing_error`
- `parser_name`
- `parser_version`

### Chunk metadata

- `chunk_index`
- `content_hash`
- `token_count`
- `page_number`
- `section_title`
- `heading_path`
- `row_number` for CSV-like sources
- `question` for FAQ sources
- `answer` for FAQ sources
- `source_title`
- `language`

### Citation metadata

- `chat_message_id`
- `chunk_id`
- `document_id`
- `document_version_id` when available
- `score`
- `quote`
- `source_title`
- `page_number` or equivalent locator when available

### Chat answer metadata

- `answer_state`
- `retrieval_score_summary`
- `model_name`
- `prompt_tokens`
- `completion_tokens`
- `latency_ms`
- `total_cost_estimate`
- `fallback_reason` when relevant

## 9. Tenant Isolation Rules

Tenant isolation is mandatory across storage, database records, vector search, citations, and chat answers.

### Storage isolation

- Object storage paths must include organisation and workspace scope.
- A worker must verify that the job's document version belongs to the expected organisation and workspace before reading source files.
- Public URLs to raw source files should not be generated for chatbot users in MVP.

### Database isolation

- Tenant-owned tables must include `organisation_id` and/or `workspace_id` according to the database design.
- Document, chunk, chat, citation, analytics, and audit queries must filter by tenant context.
- A `workspace_id` alone is not enough when organisation context is available; use both for safety.

### Retrieval isolation

Retrieval must filter by:

- `organisation_id`
- `workspace_id`
- active organisation status
- active workspace status
- document status `ready`
- current effective document version
- chunk status `ready`
- non-expired document and version
- source visibility allowed for the current channel

### Citation isolation

- Citations must point only to chunks retrieved for the same organisation and workspace as the chat session.
- Citation creation must validate `chat_message_id`, `chunk_id`, `document_id`, and document version tenant consistency.
- Historical citations may remain for previous answers, but new answers must not cite archived, expired, failed, deleted, or cross-tenant chunks.

### Chat answer isolation

- Prompt assembly must include only retrieved context from the current tenant and workspace.
- If retrieval evidence is missing or weak, the answer must use a safe fallback rather than guessing.
- Chat logs and analytics must remain tenant-scoped.

## 10. Future Connector Compatibility

Future connectors should extend source acquisition, not retrieval semantics.

### SharePoint and OneDrive

- Store external drive item IDs in metadata or future connector tables.
- Create a new document version when file content or checksum changes.
- Preserve source display name, last modified time, and source URL metadata.
- Do not retrieve directly from Microsoft APIs at chat-answer time.

### Google Drive

- Store external file IDs and drive metadata outside chunk content.
- Convert synced files into document versions before processing.
- Keep permission checks and sync credentials separate from chat retrieval.

### URL imports and web crawler

- A single URL can map to one document with one version per content snapshot.
- A crawler may create one document per page or a parent crawl collection plus page documents in a future model.
- Crawler sources must respect allowed domains, robots/policy decisions, deduplication, and crawl limits.
- Retrieved chunks must cite the page/document snapshot used at ingestion time.

### Compatibility rules

- External connector credentials must never be stored on document, chunk, citation, or chat message rows.
- Sync jobs may create versions, archive removed sources, or mark versions expired.
- Chat runtime must not need connector-specific logic to retrieve or cite knowledge.

## 11. Entity Relationships

### Conceptual flow

```text
documents
  -> document_versions
    -> chunks
      -> embeddings / embedding_vector
        -> retrieved context
          -> citations
            -> assistant chat_messages / chat answers
```

### Relationship rules

- `documents` belong to one organisation and one workspace.
- `document_versions` belong to one document and represent immutable snapshots.
- `chunks` belong to one organisation, one workspace, one document, and one document version.
- Embeddings belong to chunks, either as `chunks.embedding_vector` in MVP or as rows in a future `embeddings` table.
- Retrieval returns ranked chunks filtered by tenant and knowledge state.
- Assistant `chat_messages` store generated answers and answer state.
- `citations` link assistant messages to the chunks used as evidence.
- Citations must preserve enough metadata to explain an answer even after a document receives a newer version.

## 12. Acceptance Criteria for Future Implementation Tasks

### Document upload and FAQ tasks

- Validate source type, size, filename, and tenant context.
- Store source content in tenant-scoped storage.
- Create `documents` and immutable `document_versions` records.
- Return safe user-facing processing status.
- Audit create, archive, delete, and replacement actions.

### Ingestion worker tasks

- Process document versions asynchronously and idempotently.
- Extract text, create chunks, generate embeddings, and mark readiness only after all required work succeeds.
- Preserve tenant IDs on chunks and any embedding records.
- Exclude partial, failed, archived, expired, deleted, or private sources from retrieval.
- Store safe processing errors and operational diagnostics separately where needed.

### Retrieval tasks

- Filter vector search by organisation, workspace, active document status, effective ready version, ready chunk status, expiry, and channel visibility.
- Return chunk metadata needed for citations.
- Use safe fallback when retrieved evidence is weak or missing.
- Include tests for cross-tenant retrieval prevention.

### Citation and chat answer tasks

- Create citations only for chunks used in the answer context.
- Validate citation tenant consistency before writing records.
- Store answer state, model, latency, token, cost, and fallback metadata where available.
- Never cite unavailable or cross-tenant chunks.
- Preserve source traceability from answer to chunk, document version, and document.

### Future connector tasks

- Convert external sources into document versions before ingestion.
- Keep connector credentials and sync configuration separate from retrieval records.
- Use checksums or source modified timestamps to avoid duplicate versions.
- Preserve external IDs and source URLs in metadata without exposing secrets.
- Ensure chat retrieval remains source-type agnostic.
