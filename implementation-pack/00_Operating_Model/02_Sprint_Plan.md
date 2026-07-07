# Sprint Plan

Version: 1.0
Status: Active Draft

## Sprint model

Use short implementation sprints. Each sprint should produce working software, not only documentation.

## Sprint 0: Foundation

Goal:

Create a clean repository, backend foundation, frontend foundation, local development structure, and quality baseline.

Tasks:

- TASK-001 Complete Monorepo Foundation
- TASK-002 Backend Foundation
- TASK-003 Frontend Foundation
- TASK-004 Local Development Foundation

Exit criteria:

- Backend health endpoint works.
- Frontend app runs.
- Repository has clear workspace structure.
- Basic local development instructions exist.

## Sprint 1: Database and Tenancy

Goal:

Create the database foundation and tenant model.

Tasks:

- Database configuration
- Alembic setup
- Organisation model
- Workspace model
- User and membership model
- Tenant isolation test patterns

Exit criteria:

- Initial migration creates core tenant tables.
- Tenant-scoped database access patterns exist.
- Tests prove basic tenant isolation.

## Sprint 2: Knowledge Management

Goal:

Allow client admins to upload and manage knowledge sources.

Tasks:

- Document model
- Document upload API
- File storage abstraction
- FAQ model and API
- Document status lifecycle

Exit criteria:

- Admin can upload a file.
- Document record is created.
- Document lifecycle states work.

## Sprint 3: Ingestion and Embeddings

Goal:

Process uploaded documents into searchable chunks.

Tasks:

- Worker foundation
- Text extraction
- Chunking
- Embedding abstraction
- Vector storage

Exit criteria:

- Documents process asynchronously.
- Chunks are created with metadata.
- Search can retrieve workspace-scoped chunks.

## Sprint 4: Chat Runtime

Goal:

Create tenant-aware RAG chat responses.

Tasks:

- Chat sessions
- Message storage
- Retrieval service
- Prompt assembly
- Answer generation
- Citations
- Safe fallback

Exit criteria:

- User can ask a question.
- Answer is grounded in workspace knowledge.
- Fallback is used when knowledge is missing.

## Sprint 5: Widget MVP

Goal:

Allow clients to embed a chatbot on their website.

Tasks:

- Widget config API
- Public chat API
- Widget UI
- Branding settings
- Public key routing

Exit criteria:

- Widget loads on a test page.
- Widget talks to correct workspace.
- Widget uses branding settings.

## Sprint 6: Analytics MVP

Goal:

Show basic operational value to clients.

Tasks:

- Conversation list
- Message history
- Unanswered questions
- Usage summary
- Basic feedback

Exit criteria:

- Client admin can review recent conversations.
- Unanswered questions are visible.

## Sprint 7: Pilot Hardening

Goal:

Prepare for the first real pilot client.

Tasks:

- Rate limiting
- Security review
- Tenant isolation review
- Error handling
- Deployment guide
- Backup plan
- Pilot onboarding checklist

Exit criteria:

- One pilot client can be onboarded safely.
- Known limitations are documented.
