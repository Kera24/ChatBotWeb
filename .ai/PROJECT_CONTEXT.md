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

## Architecture-before-implementation rule

Every major feature must have an architecture task and an implementation task. The architecture task must be reviewed and approved before implementation starts. Follow `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`.

For public or external channel work, use the Public Access Layer bounded context from `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md` and ADR-0006. Do not let new channels call the RAG Orchestrator directly.

## Implementation rules

- Do not build features outside the active task.
- Do not change architecture unless the task explicitly requires it.
- Do not add dependencies casually.
- Do not commit secrets, API keys, tokens, credentials, or real client data.
- Do not expose system prompts, internal chain-of-thought, hidden instructions, or other tenants' data.
- Keep docs and code aligned when behavior changes.
- Preserve existing user work in the repository.

## Public widget security gate

No public widget endpoint, anonymous widget session, public RAG route, or embeddable widget UI may be implemented until TASK-055 and the relevant Public Access Layer architecture task are reviewed and approved.

Future public widget and external-channel work must go through the Public Access Layer. Public traffic must stay separate from dashboard APIs and internal development APIs. Public requests must not reuse dashboard authentication, development headers, or client-supplied tenant IDs. Tenant context must be resolved server-side from a public identity mapping to an active workspace and organisation.

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

## Public credential and widget configuration guardrails

TASK-057A and ADR-0007 define the future persistent credential and widget-configuration subsystem.

Guardrails for future Codex sessions:

- No public credential should be created automatically.
- No workspace becomes public by default.
- Widget public keys are public identifiers, not secrets, and never grant dashboard access.
- Secret-bearing credential values, such as partner API keys or webhook secrets, are shown once and stored only as strong hashes.
- Public credential admin paths must be tenant-scoped by organisation and workspace; never fetch credential-owned records by ID alone.
- Allowed origins must be normalised records, not arbitrary unvalidated strings.
- Public configuration responses must exclude tenant IDs, credential database IDs, policy internals, provider details, allowed-origin lists, audit metadata, internal paths, and secret hashes.

## Origin validation guardrails

TASK-058A and ADR-0008 define runtime origin-validation policy for future browser-based public channels.

Guardrails for future Codex sessions:

- Widget state-changing endpoints require a validated `Origin` before they may process public session or message requests.
- Origin validation is not authentication; it must be combined with public credential resolution, anonymous session validation, rate limiting, cost controls, and tenant-scoped RAG.
- Missing `Origin` fails closed for widget message and session endpoints.
- `Referer` fallback is disabled for state-changing widget endpoints and may be used only for future config GET when an explicit policy allows it.
- Partner API credentials use separate secret authentication rules and do not rely on browser-origin validation.
- Do not infer client origin from `Host`.
- Trust forwarded headers only from configured trusted proxies.
- Do not implement runtime origin validation, CORS changes, or public widget endpoints until TASK-058B or a later approved implementation task.

## Distributed rate limiting guardrails

TASK-059A and ADR-0009 define distributed rate-limiting policy for future public and external channels.

Guardrails for future Codex sessions:

- No public message/session endpoint may bypass the distributed limiter.
- Forwarded client-IP headers are trusted only from configured proxies.
- Short-window rate limits are separate from daily/monthly quotas.
- Security-sensitive Redis uncertainty fails closed unless architecture explicitly permits a constrained read-only fallback.
- Redis keys must not contain raw public keys, partner secrets, raw IP addresses, session tokens, message content, or PII.
- Rate-limit denial must prevent anonymous session creation, RAG orchestration, provider execution, and cost-bearing side effects.
- Do not implement Redis client code, Lua scripts, rate-limit middleware, or public runtime endpoints until TASK-059B or a later approved implementation task.

## Anonymous public session guardrails

TASK-060A and ADR-0010 define the anonymous public-session security model for future widget and browser-based public channels.

Guardrails for future Codex sessions:

- Public session tokens never contain trusted tenant IDs, workspace IDs, organisation IDs, raw conversation IDs, or other internal tenant-routing claims.
- Widget message requests must validate a credential-bound public session before any RAG orchestration or conversation append occurs.
- The browser must not submit a trusted conversation ID for public widget messages; server-side session state owns the optional conversation mapping.
- Public sessions are PostgreSQL-backed, revocable, and validated against credential, organisation, workspace, channel, environment, policy profile, and origin binding on every use.
- Session validation occurs after credential resolution, tenant resolution, request validation, origin validation, and rate-limit checks.
- No public session endpoint may be added before TASK-060A is reviewed and approved and a later implementation task explicitly authorises it.
- Raw public session tokens and token secrets must never be logged, stored in plaintext, returned after creation, or included in audit/operational events.

## Public widget session endpoint guardrails

TASK-061A and ADR-0011 define the first public widget endpoint boundary for future implementation.

Guardrails for future Codex sessions:

- The first public endpoint is session creation only: `POST /api/v1/widget/{public_key}/sessions`.
- Public session creation must use the Public Access Gateway in `session_creation` mode.
- Public session creation must not create a conversation, accept a message, call retrieval, call AI Core, or invoke RAG.
- No public route may accept tenant IDs, workspace IDs, conversation IDs, policy overrides, dashboard bearer tokens, or dashboard development headers.
- Public widget routes use no cookies and require a validated `Origin`.
- Public widget CORS must be dynamic, origin-validation-driven, and must not use wildcard origins or credentialed browser cookies.
## Public widget configuration endpoint guardrails

TASK-062A, TASK-062B, and ADR-0012 define and implement the public widget configuration delivery boundary.

Guardrails for future Codex sessions:

- Public widget configuration is delivered separately from session creation.
- Config reads must not create sessions or conversations.
- Only published sanitised configuration is public.
- Draft configuration is never publicly visible.
- Public configuration must pass Origin validation and `widget_config_read` rate limiting.
- Public widget configuration responses must not expose tenant IDs, internal credential/config IDs, allowed origins, policy internals, provider/model/prompt details, rate-limit rules, secret/hash fields, audit metadata, or internal asset paths.
## Implemented public widget endpoints

As of TASK-062B, the only implemented public widget endpoints are:

- `GET /api/v1/widget/{public_key}/config`
- `POST /api/v1/widget/{public_key}/sessions`
- Route-scoped `OPTIONS` handlers for those paths

No public widget message endpoint, public session validation endpoint, public RAG endpoint, conversation creation route, widget SDK/UI, or global CORS wildcard is implemented.
## Public widget message and RAG guardrails

TASK-063A and ADR-0013 define the future public widget message/RAG boundary.

Guardrails for future Codex sessions:

- Public messages require a validated credential-bound anonymous session.
- Public clients never choose tenant, conversation, model, provider, prompt, retrieval, context, or token limits.
- Public message processing uses Public Access Gateway before the RAG Orchestrator.
- Message slots are consumed immediately before expensive RAG processing.
- Public AI output and citations require a dedicated sanitisation boundary.
- No public message route may be added before TASK-063A approval and a later implementation task explicitly authorises it.
- Public message routes must not accept dashboard development headers, dashboard bearer tokens, tenant IDs, conversation IDs, model/provider/prompt overrides, retrieval limits, context limits, output limits, raw conversation history, file uploads, or arbitrary tools.
