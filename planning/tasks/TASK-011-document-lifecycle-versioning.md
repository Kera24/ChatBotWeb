# Task: Document Lifecycle and Versioning Planning

## Task ID

TASK-011

## Linked epic/story

- EPIC-003

## Objective

Define the document lifecycle and versioning architecture that future knowledge-management, ingestion, retrieval, citation, audit, and administration tasks must follow.

This is a planning and architecture task only. Do not implement application code, database migrations, API routes, workers, UI screens, or integrations in this task.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `implementation-pack/03_AI/02_Knowledge_Platform_Architecture.md`
- `docs/02_Architecture/02_Database_Design.md`
- `planning/tasks/TASK-010-knowledge-platform-architecture.md`

## Purpose

The document lifecycle model must ensure that knowledge sources can be safely uploaded, updated, versioned, archived, expired, deleted, processed, retrieved, cited, and audited without breaking tenant isolation or answer traceability.

A document is the stable knowledge source identity inside a workspace. A document version is an immutable processable snapshot of that document at a point in time. Chunks and embeddings are generated from document versions and must remain traceable to the version that produced them.

## Document lifecycle states

Future implementation should model document status separately from document-version processing status.

Recommended document states:

- `draft`: future optional state for manually authored content before publication.
- `uploaded`: source exists and at least one version has been created, but no ready version is active yet.
- `processing`: the latest candidate version is being processed.
- `ready`: an active ready version is available for retrieval.
- `failed`: no active ready version is available because processing failed or all usable versions are unavailable.
- `archived`: intentionally removed from normal retrieval and management views unless archive filters are used.
- `expired`: excluded from retrieval because document-level or active-version expiry passed.
- `deleted`: soft-deleted and excluded from normal workflows, retrieval, and new citations.

Recommended document version states:

- `pending`: version exists but is not yet queued.
- `queued`: version is waiting for worker processing.
- `extracting`: text extraction is running.
- `chunking`: chunk generation is running.
- `embedding`: embedding generation is running.
- `ready`: version has ready chunks and embeddings.
- `failed`: processing failed and version is not retrievable.
- `superseded`: version was replaced by a newer active version.
- `withdrawn`: future approval or moderation state for a version removed before activation.

## Versioning rules

Future implementation tasks must follow these rules:

- Version numbers increment per document and never reset.
- Document versions are immutable once processing begins.
- Re-uploading a file, editing FAQ content, or receiving changed connector content creates a new version.
- A version must store checksum or equivalent content fingerprint.
- If source content is unchanged, ingestion may skip creating a duplicate processable version.
- Chunks and embeddings belong to one document version and must not be reassigned to another version.
- A failed version remains available for diagnostics but is not retrievable.
- A superseded version may remain available for historical citations and audit traceability.
- Historical citations must continue pointing to the version used when the answer was generated.

## Active version rules

Only one active version should be retrievable for a document at a time.

Activation rules:

- A version can become active only after it reaches `ready`.
- A ready version must pass tenant, visibility, effective date, expiry, and document-status checks before retrieval.
- Activating a new version supersedes the previous active version for new retrieval.
- If a new version fails processing, the previous active ready version may remain active unless the document was explicitly archived, expired, or deleted.
- If no version is ready and eligible, the document status should not be `ready`.
- Active-version changes must be auditable.

Retrieval must filter by:

- `organisation_id`
- `workspace_id`
- document status `ready`
- active ready document version
- chunk status `ready`
- non-expired document and version
- allowed visibility for the current channel

## Archived and expired document behaviour

Archived behaviour:

- Archived documents are excluded from retrieval immediately.
- Archived documents may remain visible in administrative archive views.
- Existing historical citations may still display source titles and safe citation metadata.
- Archived documents should not create new chunks, embeddings, or citations unless restored and reprocessed where required.
- Restoring an archived document must re-check active version eligibility before retrieval resumes.

Expired behaviour:

- Expired documents or versions are excluded from retrieval automatically.
- Expiry should not delete records or object-storage files by itself.
- Expired documents may be renewed by updating expiry policy or creating a new version.
- Expiry transitions should be auditable when caused by an explicit admin action; automatic expiry should be observable through status or scheduled audit events if implemented.

## Future approval workflow design

Approval workflow is not required for MVP but the lifecycle must allow it later.

Future approval states may include:

- `draft`: content is being prepared.
- `submitted_for_review`: a contributor has submitted a version.
- `approved`: an authorised user approved activation.
- `rejected`: a reviewer rejected the candidate version.
- `withdrawn`: author or admin withdrew the candidate version.

Future approval rules:

- Approval applies to document versions, not only documents.
- A candidate version should not become active until approved where approval is enabled.
- Reviewers must have tenant-scoped membership and sufficient role permission.
- Approval decisions must create audit events with actor, timestamp, version, and decision metadata.
- Rejected versions must not create retrievable chunks or may have chunks marked `excluded` if processing happened before review.

## Deletion versus archival rules

Use archival for reversible removal and deletion for stronger removal intent.

Archival:

- Reversible by authorised users.
- Excludes document and all versions from retrieval.
- Retains source files, extracted text, chunks, embeddings, citations, and audit history unless a retention task later removes storage artifacts.
- Preferred when the client may need history, compliance visibility, or later restoration.

Deletion:

- Should be soft-delete first using `deleted_at` and status `deleted`.
- Excludes document and all versions from retrieval and normal admin lists.
- Prevents new processing, retrieval, and citation creation.
- Retains minimum metadata needed for audit, referential integrity, and historical chat/citation display.
- Physical deletion of source files, extracted text, chunks, and embeddings should be handled by a future retention/purge policy task.

Deletion must not break historical chat records. If a source is deleted, existing citations should degrade gracefully with safe metadata such as title and version reference rather than exposing inaccessible content.

## How updates affect chunks and embeddings

Document updates must create or select a document version before processing.

Update rules:

- New content creates a new version with new chunks and embeddings.
- Existing ready chunks for the previous active version remain unchanged.
- New chunks are not retrievable until the new version is ready and active.
- When a new version becomes active, future retrieval uses only chunks from that version for that document.
- Previous-version chunks may remain stored for historical citation traceability and rollback.
- If a chunking strategy or embedding model changes, future implementation may create a new version or mark embeddings `stale` and re-embed according to a dedicated reprocessing task.
- Partial update processing must not mix chunks from old and new versions in one active document version.

Embedding rules:

- Embeddings must inherit tenant, workspace, document, and version scope through their chunk relationship.
- Failed or stale embeddings must make their chunks non-retrievable.
- Embedding provider metadata should be tracked where needed for debugging and future reprocessing.

## Tenant isolation rules

Future implementation tasks must ensure:

- Every lifecycle action resolves `organisation_id`, `workspace_id`, actor, and role before data access.
- Document, version, chunk, embedding, citation, audit, and chat queries are tenant-scoped.
- Object-storage paths include organisation and workspace scope.
- Workers validate that queued document versions belong to the expected tenant before processing.
- Retrieval never uses chunks from archived, expired, deleted, failed, superseded, private, or cross-tenant versions.
- Citation writes validate that chat message, chunk, document, and document version all belong to the same organisation and workspace.
- Public widget retrieval uses public workspace identity plus active organisation/workspace status, allowed-domain checks, rate limits, and tenant-scoped retrieval filters.

## Audit event requirements

Future implementation should audit important lifecycle and versioning events.

Required audit event categories:

- `document.created`
- `document.updated_metadata`
- `document.archived`
- `document.restored`
- `document.expired`
- `document.deleted`
- `document_version.created`
- `document_version.processing_started`
- `document_version.processing_failed`
- `document_version.ready`
- `document_version.activated`
- `document_version.superseded`
- `document_version.approved_future`
- `document_version.rejected_future`

Audit events should include:

- `organisation_id`
- `workspace_id`
- `actor_user_id` where available
- action name
- entity type and entity ID
- document ID and version ID where applicable
- before/after status values where safe
- timestamp
- safe reason or failure category
- request or job correlation ID where available

Audit events must not include secrets, raw source content, full extracted text, embeddings, provider credentials, or hidden prompts.

## Edge cases

Future implementation should handle these cases explicitly:

- New version fails while previous ready version exists.
- New version succeeds while a chat answer is being generated from the old version.
- Document is archived while processing is in progress.
- Document is deleted while processing is queued or running.
- Version expires during retrieval or prompt assembly.
- Duplicate upload has the same checksum as the active version.
- Empty, corrupt, encrypted, or unsupported source file.
- File title changes without content changing.
- FAQ content changes while previous FAQ citations exist.
- Chunking or embedding settings change after previous versions exist.
- Restore archived document whose active version is expired.
- Connector future source disappears upstream.
- Cross-tenant ID is supplied accidentally or maliciously.
- Historical citation references a deleted or archived document.

## Acceptance criteria for future implementation

Document lifecycle implementation tasks must satisfy:

- Document and version statuses are separate and consistently transitioned.
- Only one active ready version is retrievable per document.
- Failed candidate versions do not corrupt or deactivate a previous ready version unless explicitly required by document state.
- Archived, expired, deleted, failed, superseded, and excluded content is not retrieved for new answers.
- Updates create immutable versions and do not mutate historical chunks or citations.
- Chunks and embeddings are always traceable to organisation, workspace, document, and version.
- Deletion is soft-delete first and does not break historical chat/citation records.
- Approval workflow extension points are documented without being implemented in MVP.
- Tenant isolation is enforced for lifecycle actions, worker jobs, retrieval, and citations.
- Audit events are recorded for lifecycle, version, activation, failure, archive, restore, expiry, and deletion actions.
- Edge cases above have tests or documented handling in implementation tasks.
- No production code, migrations, dependencies, runtime configuration, or integrations are added by this planning task.
