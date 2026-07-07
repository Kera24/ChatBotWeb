# Product Requirements Document

Version: 0.1
Status: Draft

## 1. Product overview

ChatBotWeb / Yoranix AI Platform is a multi-tenant AI knowledge platform for creating client-specific RAG chatbots and future AI agents.

The MVP focuses on allowing each client organisation to manage its own knowledge base and deploy a branded chatbot to its website without developer involvement.

## 2. Problem statement

Clients frequently request chatbots that answer questions from organisation-specific knowledge. The knowledge changes over time, and rebuilding or manually updating each chatbot is inefficient.

The platform must solve this by creating a reusable system for onboarding organisations, managing knowledge, indexing documents, answering questions, and monitoring performance.

## 3. Target users

### Super admin

A platform operator who manages all organisations, workspaces, usage, and global settings.

### Client admin

A client-side administrator who manages documents, chatbot settings, users, and analytics.

### Knowledge contributor

A staff member who can add or update knowledge but may not have full administrative access.

### End user

A public website visitor, student, customer, patient, or applicant who asks questions through the chatbot.

## 4. MVP goals

The MVP must allow:

1. Platform operators to create and manage client organisations.
2. Client admins to upload and manage knowledge.
3. The system to process knowledge into searchable chunks.
4. End users to ask questions through a website chatbot.
5. The chatbot to answer from tenant-specific knowledge only.
6. Client admins to review chat history and unanswered questions.
7. The platform to track usage and basic cost signals.

## 5. MVP non-goals

The MVP will not include:

- Billing automation
- Voice agents
- WhatsApp integration
- Microsoft Teams integration
- Advanced workflow automation
- Marketplace
- Fine-tuning
- Custom model training
- Full SSO
- Multi-region deployment

## 6. Functional requirements

### FR-001 Organisation management

Super admins must be able to create, view, update, and deactivate client organisations.

Acceptance criteria:

- An organisation has a name, status, plan placeholder, and timestamps.
- Deactivated organisations cannot serve public chatbot traffic.
- Organisation data is isolated from other organisations.

### FR-002 Workspace management

Each organisation must have at least one workspace.

Acceptance criteria:

- A workspace belongs to one organisation.
- A workspace has settings for chatbot name, branding, and public widget configuration.
- Future organisations may have multiple workspaces.

### FR-003 User and role management

The platform must support basic roles.

Required roles:

- Super admin
- Organisation owner
- Client admin
- Knowledge contributor
- Viewer

Acceptance criteria:

- Users can only access organisations they belong to.
- Super admins can access platform-level views.
- Client users cannot access other client data.

### FR-004 Knowledge upload

Client admins must be able to upload knowledge files.

MVP supported file types:

- PDF
- DOCX
- TXT
- CSV

Acceptance criteria:

- Uploaded files create document records.
- Documents show processing status.
- Failed uploads show useful error states.
- Original files are stored safely.

### FR-005 Manual FAQ management

Client admins must be able to create manual FAQ entries.

Acceptance criteria:

- FAQ entries have question, answer, category, status, and timestamps.
- Active FAQs are available to retrieval.
- Archived FAQs are excluded from retrieval.

### FR-006 Document processing

The platform must extract text, split it into chunks, generate embeddings, and store searchable records.

Acceptance criteria:

- Processing runs asynchronously.
- Chunk records preserve source metadata.
- Each chunk is scoped to tenant and workspace.
- Processing failures are visible to admins.

### FR-007 Chatbot question answering

End users must be able to ask questions through a chatbot interface.

Acceptance criteria:

- The request identifies the correct workspace.
- Retrieval only searches active knowledge for that workspace.
- The answer is generated from retrieved context.
- The response includes citations when source evidence is available.
- If evidence is insufficient, the bot gives a safe fallback.

### FR-008 Website widget

The platform must provide an embeddable website widget.

Acceptance criteria:

- The widget can be embedded using a simple script or generated install snippet.
- The widget uses the workspace's branding settings.
- The widget works on desktop and mobile.
- Public widget access is rate-limited.

### FR-009 Chat history

Client admins must be able to review chat sessions.

Acceptance criteria:

- Sessions and messages are stored.
- Admins can view recent conversations.
- Conversations are scoped to the organisation and workspace.

### FR-010 Unanswered questions

The platform must identify questions that could not be answered confidently.

Acceptance criteria:

- Low-confidence or fallback responses are flagged.
- Client admins can view unanswered questions.
- These questions can inform knowledge updates.

### FR-011 Basic analytics

The platform must provide basic analytics.

Acceptance criteria:

- Total conversations
- Total messages
- Unanswered question count
- Common questions placeholder
- Usage grouped by workspace

### FR-012 Audit events

Important administrative actions must be logged.

Acceptance criteria:

- Document upload, archive, delete, and settings changes are logged.
- Audit records include actor, action, entity, timestamp, and tenant.

## 7. Non-functional requirements

### NFR-001 Tenant isolation

No user, query, document, vector record, or analytics item may cross tenant boundaries.

### NFR-002 Availability

The MVP should target high availability for pilot customers, but full enterprise SLA is not required initially.

### NFR-003 Performance

Target response time:

- Dashboard API: under 500 ms for common operations
- Chatbot response: under 8 seconds for MVP
- Widget load: under 2 seconds after script fetch

### NFR-004 Scalability

The architecture must support future scaling to thousands of organisations by separating web, API, ingestion, RAG, and worker workloads.

### NFR-005 Security

The system must support authentication, role-based access, tenant-scoped queries, rate limiting, audit logs, and safe public widget keys.

### NFR-006 Observability

The platform must log errors, AI latency, retrieval events, model usage, and cost-relevant usage data.

### NFR-007 Maintainability

The codebase must be modular, documented, and suitable for AI-assisted development.

## 8. MVP success metrics

- Time to onboard a new client: under 30 minutes
- Time from upload to searchable document: under 5 minutes for standard small documents
- Answer citation rate: over 80 percent when knowledge exists
- Fallback rate: tracked and visible
- Cross-tenant leakage incidents: zero
- Pilot clients onboarded: at least 3 before Phase 2

## 9. Key risks

- Hallucinated answers
- Poor document extraction quality
- Old documents being used accidentally
- Cross-tenant retrieval bugs
- High LLM cost
- Widget abuse from public traffic
- Clients uploading low-quality knowledge

## 10. Open questions

1. Should the first version use pgvector only, or support Qdrant from the beginning?
2. Should authentication be custom, Clerk, Supabase Auth, or Auth.js?
3. Should public chatbot conversations collect personal data?
4. What retention period should be used for chat logs?
5. Which pilot client should be used first?
