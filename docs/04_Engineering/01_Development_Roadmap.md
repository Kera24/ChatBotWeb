# Development Roadmap

Version: 0.1
Status: Draft

## Roadmap principle

Build the smallest reliable platform that proves repeatable client onboarding, tenant-aware RAG, and website chatbot deployment.

Do not build advanced agents before the knowledge platform and chatbot runtime are stable.

## Phase 1: Foundation documentation

Deliverables:

- Project charter
- Product vision
- Product requirements document
- Software requirements specification
- System architecture
- RAG architecture
- Database design
- API specification
- Design system
- Security model
- Testing strategy
- MVP task breakdown

Outcome:

The repository becomes ready for AI-assisted development using Codex, Cursor, or another coding agent.

## Phase 2: Repository skeleton

Deliverables:

- Next.js frontend skeleton
- FastAPI backend skeleton
- Shared types package
- UI package
- Docker Compose
- PostgreSQL setup
- Redis setup
- Basic CI workflow

Outcome:

Developers can run the platform locally.

## Phase 3: Core SaaS foundation

Features:

- Authentication
- Organisation model
- Workspace model
- Tenant resolution
- Role-based access control
- Super-admin shell
- Client-admin shell

Outcome:

The system can represent multiple client organisations safely.

## Phase 4: Knowledge management MVP

Features:

- Document upload
- File storage
- Document list
- Document status
- Delete document
- Archive document
- Manual FAQ creation

Outcome:

Clients can manage knowledge sources.

## Phase 5: RAG MVP

Features:

- Text extraction
- Chunking
- Embedding generation
- Vector storage
- Tenant-filtered retrieval
- Answer generation
- Source citations
- Failed answer handling

Outcome:

The platform can answer questions from client-specific knowledge bases.

## Phase 6: Chatbot widget MVP

Features:

- Embeddable script
- Tenant public key
- Chat UI
- Branding settings
- Suggested questions
- Public chat API
- Rate limiting

Outcome:

A client can embed the chatbot on their website.

## Phase 7: Analytics MVP

Features:

- Chat sessions
- Message logs
- Top questions
- Unanswered questions
- User feedback
- Usage per tenant
- Cost estimates

Outcome:

Clients can see what users ask and where knowledge gaps exist.

## Phase 8: Production hardening

Features:

- Audit logs
- Better permissions
- Error monitoring
- Observability
- Evaluation datasets
- Regression tests
- Backup strategy
- Deployment documentation

Outcome:

The MVP becomes suitable for pilot customers.

## Phase 9: Integrations

Future features:

- Website crawler
- SharePoint sync
- OneDrive sync
- Google Drive sync
- Email handover
- CRM integration
- Calendar booking

## Phase 10: Agent platform

Future features:

- Router agent
- Knowledge agent
- Clarification agent
- Tool agent
- Escalation agent
- Evaluation agent

Outcome:

The product evolves from chatbot platform to AI agent platform.
