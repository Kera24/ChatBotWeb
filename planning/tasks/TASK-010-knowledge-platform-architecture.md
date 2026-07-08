# Task: Knowledge Platform Architecture Planning

## Task ID

TASK-010

## Linked epic/story

- EPIC-003

## Objective

Define the knowledge platform architecture that will guide future document upload, versioning, ingestion, retrieval, citation, and answer-grounding implementation.

This is a planning and architecture task only. Do not implement application code, database migrations, API routes, workers, UI screens, or integrations in this task.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `implementation-pack/03_AI/01_RAG_Implementation_Standards.md`
- `docs/03_AI/01_RAG_Architecture.md`
- `docs/02_Architecture/02_Database_Design.md`
- `docs/07_Roadmap/01_MVP_Implementation_Plan.md`

## Deliverables

- Create `implementation-pack/03_AI/02_Knowledge_Platform_Architecture.md`.
- Update `.ai/CURRENT_SPRINT.md` so TASK-010 is the current planning task.
- Keep all output as architecture/planning documentation only.

## Architecture areas to define

The implementation-pack document must define:

- Knowledge platform purpose and MVP scope.
- Supported document source types for MVP and future integrations.
- Document lifecycle from creation through archive, expiry, deletion, and replacement.
- Versioning model for `documents` and `document_versions`.
- Ingestion pipeline from source acquisition to chunks and embeddings.
- Processing states for documents, versions, chunks, and embeddings.
- Retry and failure handling model.
- Metadata model for documents, versions, chunks, citations, and answers.
- Tenant isolation rules for storage, database access, retrieval, citations, and chat answers.
- Future compatibility with SharePoint, OneDrive, Google Drive, URL imports, and web crawlers.
- Relationships between `documents`, `document_versions`, `chunks`, `embeddings`, `citations`, and chat answers.
- Acceptance criteria for future implementation tasks.

## Required architectural decisions

- `documents` represent the stable knowledge source identity inside a workspace.
- `document_versions` represent immutable processable snapshots of a source.
- Retrieval must use only active, ready, tenant-scoped chunks from the currently effective document version.
- Chat answers must cite chunks, not raw files, while retaining traceability back to document and version.
- Future external sources must fit the same document/version/chunk/embedding model without changing chat retrieval semantics.

## Tenant isolation requirements

Future implementation tasks must ensure:

- Every document and chunk query is scoped by `organisation_id` and `workspace_id`.
- Object storage paths are tenant-scoped and never shared across tenants.
- Vector search filters by organisation, workspace, active document status, effective version, chunk status, and expiry.
- Citations cannot reference chunks outside the current chat session tenant context.
- Failed, archived, expired, deleted, private, or out-of-scope knowledge is excluded from retrieval.

## Out of scope

- Database migrations.
- API endpoint implementation.
- Background worker implementation.
- Frontend upload or document management UI.
- Embedding provider integration.
- SharePoint, OneDrive, Google Drive, URL import, or crawler implementation.
- Production storage bucket configuration.

## Acceptance criteria

- `implementation-pack/03_AI/02_Knowledge_Platform_Architecture.md` exists and covers all architecture areas listed above.
- The architecture aligns with `docs/03_AI/01_RAG_Architecture.md` and `docs/02_Architecture/02_Database_Design.md`.
- The architecture preserves tenant isolation and source-grounding requirements.
- The architecture clearly distinguishes MVP upload/FAQ sources from future external sync sources.
- The architecture gives future implementation tasks clear acceptance criteria.
- `.ai/CURRENT_SPRINT.md` lists TASK-010 as the current planning task.
- No production code, migrations, dependencies, or runtime configuration are changed.
