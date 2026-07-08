# Task: Metadata and Vector Schema

## Task ID

TASK-014

## Linked epic/story

- EPIC-003

## Objective

Define a comprehensive engineering specification for metadata and vector schema used by documents, document versions, chunks, embeddings, retrieval filters, citations, auditability, and future vector-store migration.

This is an architecture-only task. Do not implement application code, database migrations, API routes, worker code, vector indexes, UI, or external integrations in this task.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `implementation-pack/03_AI/02_Knowledge_Platform_Architecture.md`
- `planning/tasks/TASK-010-knowledge-platform-architecture.md`
- `planning/tasks/TASK-011-document-lifecycle-versioning.md`
- `planning/tasks/TASK-012-ingestion-pipeline-design.md`
- `planning/tasks/TASK-013-chunking-strategy.md`
- `docs/02_Architecture/02_Database_Design.md`

## 1. Purpose

The metadata and vector schema defines how knowledge records are stored, filtered, embedded, retrieved, cited, audited, and migrated as the platform grows.

The schema must support:

- Tenant-isolated retrieval.
- Active document/version filtering.
- Source-grounded citations.
- Chunk-level vector search.
- Document lifecycle and versioning.
- MVP pgvector storage.
- Future Qdrant or external vector-store migration.
- Cost, storage, observability, and audit requirements.

Core relationship:

```text
documents -> document_versions -> chunks -> embedding_vector -> retrieval -> citations -> chat answers
```

## 2. Chunk metadata model

Chunks are the primary retrievable knowledge units. Each chunk must include structured columns for required filters and a flexible metadata object for source-specific details.

Required chunk fields:

- `id`
- `organisation_id`
- `workspace_id`
- `document_id`
- `document_version_id`
- `chunk_index`
- `content`
- `content_hash`
- `token_count`
- `metadata_json`
- `embedding_vector`
- `status`
- `created_at`

Required metadata keys:

- `source_type`
- `source_title`
- `chunking_strategy_version`
- `language`
- `heading_path` where available
- `section_title` where available
- `page_number` or source locator where available
- `parser_name` where available
- `parser_version` where available

Source-specific metadata keys:

- PDF: `page_number`, `page_range`, `pdf_block_id`, `is_header_footer_candidate`
- DOCX: `heading_path`, `paragraph_range`, `list_context`, `table_index`
- TXT: `paragraph_range`, `inferred_section_title`
- CSV: `row_number`, `row_range`, `column_names`, `table_index`
- FAQ: `faq_id`, `faq_question`, `faq_category`, `faq_tags`
- Future web: `source_url`, `canonical_url`, `crawl_id`, `page_title`
- Future drive connectors: `external_file_id`, `external_revision_id`, `source_last_modified_at`

Metadata rules:

- Required retrieval filters should be first-class columns, not only JSON keys.
- JSON metadata is for source details, display details, and future extensibility.
- Metadata must not contain secrets, connector credentials, signed URLs, hidden prompts, or raw private tokens.
- Metadata must not be trusted as the sole tenant-isolation source; use columns for tenant filters.

## 3. Document metadata model

Documents represent stable source identity. Document versions represent immutable processable snapshots.

Recommended document fields:

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

Recommended document metadata keys:

- `source_display_name`
- `description`
- `language`
- `tags`
- `external_source_id_future`
- `external_source_url_future`
- `connector_type_future`
- `retention_policy_key_future`

Recommended document version fields:

- `id`
- `document_id`
- `version_number`
- `original_file_path`
- `extracted_text_path`
- `checksum`
- `processing_status`
- `processing_error`
- `effective_from`
- `expires_at`
- `created_at`
- `created_by_user_id`

Recommended document version metadata keys:

- `source_last_modified_at`
- `source_size_bytes`
- `mime_type`
- `parser_name`
- `parser_version`
- `chunking_strategy_version`
- `embedding_model`
- `embedding_dimension`
- `processing_correlation_id`
- `failure_category`

Document metadata rules:

- Stable identity and status belong on `documents`.
- Processing snapshots and checksums belong on `document_versions`.
- Source storage paths belong on versions, not chunks.
- Connector credentials never belong on documents or versions.

## 4. Vector storage strategy

Vectors represent embeddings generated from chunk content.

MVP strategy:

- Store one embedding vector per retrievable chunk.
- Use PostgreSQL with pgvector first.
- Keep vector storage close to chunk metadata for simpler tenant-filtered retrieval.
- Use chunk status and document/version status to prevent partial or invalid retrieval.

Vector storage must support:

- Similarity search within one workspace.
- Filtering by organisation, workspace, document status, version, chunk status, expiry, and visibility.
- Citation traceability from vector result to chunk, document version, and document.
- Future embedding-model migration or re-embedding.

Embedding metadata to track:

- embedding model name
- embedding provider identifier
- embedding dimension
- embedding created timestamp
- embedding status if separated later
- token count and cost estimate where available

## 5. pgvector MVP approach

The MVP should use `chunks.embedding_vector` with pgvector.

Recommended approach:

- Store vectors directly on the `chunks` table for MVP simplicity.
- Use first-class columns for tenant and status filtering.
- Use JSON metadata for source-specific citation/display fields.
- Create vector indexes after baseline table shape is stable.
- Keep retrieval queries tenant-filtered before or during vector similarity ranking.

Expected query filters:

- `chunks.organisation_id = current_organisation_id`
- `chunks.workspace_id = current_workspace_id`
- `chunks.status = ready`
- `documents.status = ready`
- `document_versions.processing_status = ready`
- active/effective version condition
- `document_versions.expires_at IS NULL OR expires_at > now()`
- document visibility is allowed for channel

Potential pgvector index types:

- HNSW for production-like similarity search once data volume justifies it.
- IVFFlat only after enough rows exist and operational tuning is understood.
- Exact search may be acceptable for very small pilot datasets.

## 6. Qdrant future approach

Qdrant is a future option only if pgvector scale, performance, isolation, or operational requirements exceed PostgreSQL comfort.

Future Qdrant payload should include:

- `chunk_id`
- `organisation_id`
- `workspace_id`
- `document_id`
- `document_version_id`
- `document_status`
- `version_status`
- `chunk_status`
- `expires_at`
- `visibility`
- `source_type`
- `source_title`
- citation locator metadata

Future Qdrant rules:

- PostgreSQL remains the system of record.
- Qdrant stores vectors and filter payloads, not authoritative lifecycle state.
- Writes to Qdrant must be synchronized from committed chunk/version state.
- Retrieval results must be validated against PostgreSQL when consistency is uncertain.
- Tenant filters must be applied in Qdrant payload filters and validated by application logic.
- Deletions, archives, expiries, and superseded versions must update or exclude Qdrant payloads.

Migration to Qdrant should require a dedicated architecture and implementation task.

## 7. Tenant isolation filters

Tenant isolation filters are mandatory and must use first-class columns where possible.

Required filters:

- `organisation_id`
- `workspace_id`
- active organisation status
- active workspace status
- document status
- document version processing status
- active document version
- chunk status
- expiry
- channel visibility

Rules:

- Never rely on vector similarity alone to isolate tenants.
- Never retrieve chunks by `workspace_id` alone when organisation context is available.
- Workers and retrieval code must validate that chunk, document, version, and chat session share tenant context.
- Public widget retrieval must additionally enforce public workspace status, allowed domains, rate limits, and abuse controls.

## 8. Active, archived, and expired filtering

Retrieval must include only active ready content.

Include chunks only when:

- organisation is active
- workspace is active
- document status is `ready`
- document is not archived
- document is not deleted
- document is not expired
- document version is ready
- document version is active/effective
- document version is not expired
- chunk status is `ready`
- source visibility allows the current channel

Exclude chunks when:

- document is `uploaded`, `processing`, `failed`, `archived`, `expired`, or `deleted`
- version is `pending`, `queued`, `extracting`, `chunking`, `embedding`, `failed`, `superseded`, or `withdrawn`
- chunk is `pending`, `embedding`, `failed`, or `excluded`
- document or version expiry has passed
- tenant context does not match

Historical citations may reference archived, expired, deleted, or superseded material for prior answers, but new retrieval must not.

## 9. Versioning rules

Versioning must preserve answer traceability and prevent mixed-version retrieval.

Rules:

- Chunks belong to exactly one document version.
- Embeddings belong to exactly one chunk and therefore one document version.
- Chunk IDs must not be reused across versions.
- `chunk_index` may restart per document version.
- A new document version creates new chunks and embeddings.
- A ready version becomes retrievable only after activation.
- Superseded versions remain stored for audit and historical citations but are not used for new retrieval.
- Failed candidate versions must not deactivate the previous ready version unless document state requires it.
- Citations should preserve document ID, document version ID where available, chunk ID, score, and quote.

## 10. Indexing strategy

Indexes must support tenant filtering, document management, retrieval, citations, and audit queries.

Recommended relational indexes:

- `documents(organisation_id, workspace_id, status)`
- `documents(organisation_id, workspace_id, source_type)`
- `documents(workspace_id, archived_at)`
- `documents(workspace_id, deleted_at)`
- `document_versions(document_id, version_number)`
- `document_versions(document_id, processing_status)`
- `document_versions(document_id, effective_from, expires_at)`
- `chunks(organisation_id, workspace_id, status)`
- `chunks(document_id, document_version_id)`
- `chunks(document_version_id, chunk_index)`
- `chunks(content_hash)` where duplicate detection requires it
- `citations(organisation_id, workspace_id, chat_message_id)`
- `citations(chunk_id)`

Recommended vector index:

- pgvector index on `chunks.embedding_vector` once dataset size requires it.

Indexing rules:

- Prioritize tenant-filtered query patterns.
- Avoid over-indexing early MVP tables before real query patterns are known.
- Use partial indexes for `status = ready` only if implementation and migration complexity are justified.
- Revisit indexes after pilot ingestion volume is measured.

## 11. Search filters

Search filters define what the retriever may query.

Required search filters:

- organisation ID
- workspace ID
- active organisation/workspace status
- document status ready
- active ready document version
- chunk status ready
- non-expired document/version
- source type when user or product scope requires it
- visibility/channel access

Optional future filters:

- category
- language
- tag
- date/effective range
- source connector
- document ID allow-list
- document ID deny-list
- content sensitivity classification

Search filter rules:

- Product filters may narrow retrieval but must not bypass tenant filters.
- User-supplied filters must be validated against the current tenant.
- If filters produce no evidence, chat should use safe fallback rather than ungrounded answers.

## 12. Citation support

Citation support requires chunk metadata and stable relationships.

Citation records should support:

- assistant chat message ID
- chunk ID
- document ID
- document version ID where available
- organisation ID
- workspace ID
- score
- quote or short excerpt
- source title
- locator metadata such as page, row, heading, FAQ question, or URL
- created timestamp

Citation rules:

- Citations link answers to chunks used as evidence.
- Citations must validate tenant consistency before write.
- Citations must not rely only on mutable document title for traceability.
- Citations should remain explainable if a document is later superseded, archived, expired, or soft-deleted.
- Citation excerpts must be short and safe for display.

## 13. Auditability

Metadata and vector schema must support auditability of ingestion, processing, retrieval, and lifecycle changes.

Audit-relevant fields:

- actor user ID for document/version creation where available
- processing correlation ID
- source checksum
- parser version
- chunking strategy version
- embedding model and dimension
- document status transitions
- version status transitions
- active-version changes
- archive, restore, expiry, and delete actions

Audit rules:

- Audit events should store before/after state where safe.
- Audit events must not store raw source content, full extracted text, embeddings, secrets, or hidden prompts.
- Retrieval and citation records should be sufficient to reconstruct why an answer cited a source.
- Operational logs should complement audit events but not replace them.

## 14. Cost and storage considerations

Primary storage costs:

- original source files
- extracted text artifacts
- chunk text
- metadata JSON
- embedding vectors
- vector indexes
- historical versions retained for citations

Cost controls:

- checksum-based duplicate detection
- file size limits
- chunk count limits per document/version
- exclusion of low-value chunks
- avoiding re-embedding unchanged content
- retention policies for old extracted text and vectors
- tenant/workspace usage metrics
- future quotas by plan or workspace

Vector-specific costs:

- Higher embedding dimensions increase storage and index cost.
- Overlap increases chunk count and embedding cost.
- Historical version retention increases vector storage.
- Qdrant future operation adds infrastructure and synchronization costs.

## 15. Migration considerations

Schema migration must preserve tenant isolation and citation traceability.

Migration concerns:

- Adding embedding dimensions or changing embedding model.
- Moving from direct `chunks.embedding_vector` to a separate `embeddings` table.
- Moving from pgvector to Qdrant.
- Backfilling document version IDs into citations if missing in MVP.
- Adding active-version fields or status enums.
- Normalizing JSON metadata into first-class columns after query patterns mature.

Migration rules:

- Do not break historical citations.
- Keep PostgreSQL as source of truth during vector-store migration.
- Re-embedding should create traceable metadata about model and strategy changes.
- Run migrations tenant-safely and avoid cross-tenant batch mistakes.
- Plan rollback for vector index changes separately from relational schema changes.

## 16. Edge cases

Future implementation must handle:

- Chunk exists without embedding because embedding failed.
- Embedding exists for chunk later marked excluded.
- Document is archived while vector query is running.
- Document version is superseded during chat answer generation.
- Citation points to chunk from superseded version.
- Document is soft-deleted after a chat answer cited it.
- Expiry happens between retrieval and answer generation.
- Duplicate chunks across versions.
- Same content appears in multiple documents in same workspace.
- Same document title exists in multiple tenants.
- Metadata JSON missing optional locator fields.
- Embedding model dimension changes.
- pgvector index needs rebuild after model migration.
- Qdrant payload is stale compared with PostgreSQL.
- User-supplied filter references document outside tenant.

## 17. Security risks

Security risks:

- Cross-tenant vector retrieval due to missing filters.
- JSON metadata used as trusted tenant context.
- Stale vectors from archived, expired, deleted, or superseded documents remain retrievable.
- Connector secrets accidentally stored in document metadata.
- Signed object-storage URLs logged or stored in citations.
- Prompt-injection text in chunks treated as system instructions.
- Sensitive source metadata exposed through citations or logs.
- User-provided filters bypass access checks.

Mitigations:

- Use first-class tenant columns for filters.
- Validate tenant consistency before chunk, citation, and retrieval operations.
- Keep lifecycle status filters mandatory in retriever code.
- Keep connector credentials in dedicated secret storage, not metadata JSON.
- Treat chunk content as untrusted context during prompt assembly.
- Use safe citation excerpts and display metadata.
- Add tenant-isolation tests for vector retrieval.

## 18. Acceptance criteria

Future metadata/vector implementation must satisfy:

- Chunks include first-class tenant, document, version, status, content, hash, token, metadata, and vector fields.
- Documents and versions preserve stable source identity and immutable processing snapshots.
- pgvector MVP strategy supports tenant-filtered retrieval in PostgreSQL.
- Qdrant future strategy is documented as optional and keeps PostgreSQL as source of truth.
- Retrieval filters exclude inactive, archived, expired, deleted, failed, superseded, private, and cross-tenant content.
- Versioning rules prevent mixed-version retrieval.
- Citation records can trace answers to chunk, document version, document, workspace, and organisation.
- Indexing strategy supports tenant-scoped management and retrieval queries.
- Auditability covers lifecycle, processing, activation, embedding, and citation traceability.
- Storage and cost tradeoffs are documented.
- Migration paths preserve historical citations and tenant isolation.
- Security risks are identified with mitigations.
- No code, migrations, dependencies, runtime configuration, or integrations are added by this planning task.

## 19. Future implementation tasks

Recommended future implementation sequence:

1. Finalize MVP document, document version, chunk, and citation table fields.
2. Add processing and lifecycle status enums or constrained values.
3. Add first-class tenant and status indexes for documents and chunks.
4. Add pgvector extension and MVP vector field migration.
5. Add embedding metadata fields or metadata JSON keys.
6. Add active-version tracking strategy.
7. Implement tenant-filtered vector retrieval query.
8. Add citation fields for document version and locator metadata where needed.
9. Add audit event coverage for lifecycle, processing, and activation.
10. Add metadata validation for source-specific chunk metadata.
11. Add tests for archived, expired, deleted, failed, superseded, and cross-tenant filtering.
12. Add metrics for vector storage, chunk counts, and embedding cost.
13. Evaluate whether JSON metadata should be partially normalized after pilot usage.
14. Create a separate Qdrant migration ADR only if pgvector limits are reached.
