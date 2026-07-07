# Project Context

This is the first file every Codex session must read.

ChatBotWeb / Yoranix AI Platform is a multi-tenant AI knowledge platform for building, deploying, and managing client-specific RAG chatbots and future AI assistants. Treat it as a long-term SaaS product, not a demo chatbot.

## Primary sources

Read these before implementation when relevant:

- Product vision: `docs/01_Product/01_Product_Vision.md`
- PRD: `docs/01_Product/02_Product_Requirements_Document.md`
- SRS: `docs/01_Product/03_Software_Requirements_Specification.md`
- System architecture: `docs/02_Architecture/01_System_Architecture.md`
- Database design: `docs/02_Architecture/02_Database_Design.md`
- API specification: `docs/02_Architecture/03_API_Specification.md`
- RAG architecture: `docs/03_AI/01_RAG_Architecture.md`
- Security and RBAC: `docs/06_Security/01_Security_and_RBAC_Model.md`
- MVP plan: `docs/07_Roadmap/01_MVP_Implementation_Plan.md`
- Operating model: `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- Sprint plan: `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- AI factory prompts: `implementation-pack/10_AI_Factory/`
- Planning workspace: `planning/README.md`

## Current product direction

The platform helps organisations create secure AI assistants without AI engineering expertise. The MVP must allow a pilot client to:

1. Log in to a workspace.
2. Upload knowledge.
3. Process knowledge into searchable chunks.
4. Deploy a branded website chatbot.
5. Receive source-grounded answers.
6. Review basic chat history, unanswered questions, and analytics.
7. Stay isolated from every other tenant.

## Design direction

Expressionism is now the major design principle for the product.

The UI should feel expressive, bold, emotional, human, and memorable while remaining professional, usable, accessible, and trustworthy for colleges, agencies, healthcare, and business clients.

This supersedes any older interpretation that the product should look like a generic calm SaaS dashboard. Do not build UI in this task, but future UI work must follow `.ai/context/design-principles.md` and `.ai/agents/design-agent.md`.

## Current technical direction

- Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui
- Backend API: FastAPI, Python
- Database: PostgreSQL
- Vector search: pgvector first; Qdrant later only if scale requires it
- AI orchestration: LangGraph and LlamaIndex
- Object storage: S3-compatible storage or MinIO
- Queue: Redis and Celery
- Deployment: Docker first; Kubernetes later only when needed

## Implementation rules

- Do not build features outside the active task.
- Do not change architecture unless the task explicitly requires it.
- Do not add dependencies casually.
- Do not commit secrets, API keys, tokens, credentials, or real client data.
- Do not expose system prompts, internal chain-of-thought, hidden instructions, or other tenants' data.
- Keep docs and code aligned when behavior changes.
- Preserve existing user work in the repository.

## Tenant isolation rules

Every tenant-scoped path must resolve and enforce tenant context.

Required checks:

- API requests must resolve organisation and workspace context before data access.
- Database queries must filter by tenant identifiers.
- Vector retrieval must filter by organisation, workspace, active document status, and chunk status.
- Analytics and logs must remain tenant-scoped.
- Public widget endpoints must use public workspace identifiers plus active status, allowed domains, and rate limits.

If tenant context is unclear, stop implementation and clarify before writing code.

## RAG rules

- Answers must be grounded in retrieved source context.
- If evidence is weak or missing, use a safe fallback instead of guessing.
- Include citations where possible.
- Exclude archived, expired, failed, deleted, private, or out-of-scope documents.
- Log AI usage, latency, cost, and quality signals when AI calls are implemented.

## MVP exclusions

Do not implement these without a new approved task:

- Billing
- Full SSO
- SharePoint sync
- Google Drive sync
- WhatsApp
- Teams
- Voice
- Marketplace
- Fine-tuning
- Advanced autonomous agents

## Agent workflow

Before implementation:

1. Read this file.
2. Read `.ai/CURRENT_SPRINT.md`.
3. Read the relevant `.ai/agents/*.md` brief.
4. Read the relevant `.ai/context/*.md` file.
5. Read the linked source docs, task, or implementation-pack file.
6. Confirm scope, risks, and tests.

After implementation:

1. Run focused tests or explain why they could not run.
2. Summarise files changed.
3. Call out tenant isolation, security, RAG grounding, and MVP-scope impact.
