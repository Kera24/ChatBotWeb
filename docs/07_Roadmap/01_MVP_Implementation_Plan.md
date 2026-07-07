# MVP Implementation Plan

Version: 0.1
Status: Draft

## 1. MVP objective

Build a working multi-tenant AI knowledge platform that allows a pilot client to upload knowledge, deploy a branded website chatbot, receive source-grounded answers, and review basic analytics without custom engineering.

## 2. MVP success definition

The MVP is successful when:

1. A platform operator can create a client organisation.
2. A client admin can access a workspace dashboard.
3. The client can upload documents and FAQs.
4. The system can process knowledge into searchable chunks.
5. The chatbot can answer from only that workspace's knowledge.
6. The chatbot can be embedded on a website.
7. Chat sessions and unanswered questions are visible in the dashboard.
8. Tenant isolation is enforced across API, database, and retrieval.

## 3. Delivery phases

### Phase A: Repository and local development foundation

Scope:

- Monorepo folder structure
- Backend app skeleton
- Frontend app skeleton
- Widget app skeleton
- Shared packages
- Docker-based local development placeholder
- Documentation index

Definition of done:

- A developer can understand the repository structure.
- Each major folder has a README.
- Backend and frontend technology choices are documented.

### Phase B: Backend foundation

Scope:

- FastAPI application
- Health endpoint
- Configuration module
- API version prefix
- Database connection placeholder
- Modular router structure
- Basic test structure

Definition of done:

- API can start locally.
- `/health` returns an OK response.
- Project layout supports future modules.

### Phase C: Frontend foundation

Scope:

- Next.js app shell
- Dashboard layout
- Navigation placeholders
- Design system setup plan
- Pages for overview, knowledge base, chatbot settings, analytics, and users

Definition of done:

- Frontend can start locally.
- Dashboard routes exist as placeholders.
- UI direction matches the design system document.

### Phase D: Data model and migrations

Scope:

- SQLAlchemy or SQLModel models
- Alembic migrations
- PostgreSQL schema
- Tenant-scoped entities

Core entities:

- organisations
- workspaces
- users
- memberships
- documents
- document_versions
- chunks
- widget_settings
- chat_sessions
- chat_messages
- citations
- audit_events
- analytics_events

Definition of done:

- Database can be created locally.
- First migration creates MVP tables.
- Tenant-scoped tables include organisation or workspace IDs.

### Phase E: Knowledge management

Scope:

- Document upload API
- File storage abstraction
- Document list API
- Document status tracking
- FAQ creation API
- Archive and delete actions

Definition of done:

- Client admin can upload and list knowledge sources.
- Documents move through expected status states.

### Phase F: Ingestion and embeddings

Scope:

- Background worker
- Text extraction for PDF, DOCX, TXT, CSV
- Chunking
- Embedding generation abstraction
- Vector storage

Definition of done:

- Uploaded documents are processed asynchronously.
- Chunks are created with metadata.
- Retrieval can search chunks by workspace.

### Phase G: Chat runtime

Scope:

- Chat session creation
- Message API
- Tenant-aware retrieval
- Prompt assembly
- LLM response generation
- Citations
- Safe fallback

Definition of done:

- End users can ask questions.
- Answers are grounded in retrieved context.
- The system refuses or falls back when context is insufficient.

### Phase H: Website widget

Scope:

- Embeddable widget app
- Public widget config endpoint
- Public session endpoint
- Public message endpoint
- Workspace public key
- Branding support

Definition of done:

- A client can copy an embed snippet into a website.
- The widget loads the correct workspace config.
- The widget sends and receives messages.

### Phase I: Analytics and operations

Scope:

- Conversation history
- Message logs
- Unanswered questions
- Usage counts
- Audit events

Definition of done:

- Client admins can view recent conversations.
- Low-confidence and fallback questions are visible.
- Administrative changes are logged.

### Phase J: Pilot readiness

Scope:

- Security review
- Tenant isolation tests
- Rate limiting
- Error handling
- Basic deployment guide
- Pilot onboarding checklist

Definition of done:

- One pilot client can be onboarded safely.
- Known limitations are documented.

## 4. Implementation order

1. Repository skeleton
2. Backend skeleton
3. Frontend dashboard skeleton
4. Database schema
5. Organisation and workspace APIs
6. Auth and RBAC
7. Document upload
8. Ingestion worker
9. Embeddings and retrieval
10. Chat API
11. Widget
12. Analytics
13. Hardening

## 5. MVP exclusions

Do not implement in MVP:

- Billing
- Full SSO
- SharePoint sync
- Google Drive sync
- WhatsApp
- Teams
- Advanced agents
- Voice
- Marketplace
- Fine-tuning

## 6. Engineering standards

- TypeScript for frontend and shared web packages
- Python for backend and AI services
- REST API first
- Tenant ID required on tenant-scoped records
- Background processing for long-running tasks
- Tests required for tenant isolation and permission checks
- AI calls must be logged for cost and latency

## 7. Pilot checklist

Before onboarding a pilot client:

- Create organisation
- Create workspace
- Configure widget settings
- Upload test documents
- Run test questions
- Verify citations
- Verify fallback behaviour
- Verify tenant isolation
- Embed widget on test page
- Review chat logs
- Review unanswered questions

## 8. Next implementation task

Create the repository monorepo skeleton and lightweight starter apps.
