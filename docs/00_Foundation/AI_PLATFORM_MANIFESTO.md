# AI Platform Manifesto

Version: 1.0
Status: Active

## Mission

Build a reusable, secure, multi-tenant AI platform that allows organisations to transform their changing knowledge into reliable assistants, search experiences, workflows, and future AI agents.

This repository is not a one-off chatbot project. It is the foundation of Yoranix AI Core: a shared intelligence layer that can power website assistants, internal staff assistants, Microsoft Teams and Slack integrations, workflow automation, voice interfaces, and future agentic systems.

## Product promise

An organisation should be able to create a workspace, add or connect knowledge, deploy an assistant, update that knowledge without developer intervention, and understand how the assistant is performing.

## Architectural principles

### Platform before channel

The knowledge, retrieval, prompt, provider, conversation, evaluation, and cost systems must remain independent of any single interface. A website widget is one channel, not the platform itself.

### Multi-tenant by construction

Tenant isolation is not an optional security layer. It is a foundational invariant across relational data, object storage, vector search, retrieval, audit events, analytics, and model execution.

No tenant-scoped resource may be fetched using only its resource identifier when organisation or workspace context is required.

### Source-grounded intelligence

The platform must prefer an honest fallback over an unsupported answer. RAG answers must use approved, active, tenant-scoped knowledge and preserve citation-ready evidence.

### Provider independence

Core product behaviour must not depend directly on one model provider. Providers, models, prompts, token accounting, retries, timeouts, and costs must be separated behind stable interfaces.

### Reusable AI Core

Capabilities that can support multiple products belong in reusable platform layers. Application-specific presentation and workflows belong in application layers.

### Explicit lifecycle and versioning

Documents, versions, chunks, embeddings, prompts, models, and evaluations require explicit lifecycle states and traceability. Active production behaviour must be reproducible from versioned inputs.

### Observable and cost-aware

Every AI operation must be designed for measurement. The platform should be able to trace latency, provider, model, prompt version, token usage, estimated cost, retrieval evidence, failures, and user feedback.

### Secure defaults

Secrets must never be committed. Public endpoints require abuse controls. Uploaded files are untrusted. User questions and retrieved documents may contain prompt injection attempts. Access must follow least privilege.

### Evolution without premature complexity

The architecture must preserve future options without implementing enterprise complexity before it is needed. Start with modular boundaries, clear interfaces, and tests; extract services only when operational scale justifies it.

## Design philosophy: controlled Expressionism

Expressionism is the major visual design principle of the product.

The interface should feel bold, emotional, human, memorable, and distinct from generic SaaS dashboards. It may use expressive typography, asymmetric composition, confident scale, visual tension, layered shapes, meaningful motion, and emotionally resonant illustrations.

Expressionism must remain controlled by five constraints:

1. Usability is never sacrificed for visual novelty.
2. Trust-critical information remains calm, legible, and unambiguous.
3. Accessibility and contrast remain mandatory.
4. Tenant branding may influence expression without breaking the product system.
5. Motion communicates state and hierarchy rather than becoming decoration.

The result should feel expressive and alive while remaining suitable for education, healthcare, professional services, and regulated organisations.

## AI safety principles

- Do not invent knowledge when evidence is absent.
- Clearly separate retrieved facts from generated explanation.
- Preserve source attribution.
- Reject cross-tenant retrieval paths.
- Treat uploaded knowledge and user content as untrusted input.
- Log failures without leaking secrets or private content unnecessarily.
- Keep human escalation available for uncertain or sensitive cases.
- Avoid collecting personal data that is not required for the service.

## Engineering non-negotiables

1. Every implementation task must have acceptance criteria and test expectations.
2. Tenant-scoped reads and writes must include validated tenant context.
3. Public widget APIs must remain separate from authenticated dashboard APIs.
4. Business logic must not accumulate inside API route handlers.
5. Long-running ingestion work must move to background processing.
6. Prompt templates and model configurations must be versionable.
7. Provider-specific behaviour must remain behind adapters.
8. Critical retrieval and permission behaviour must have automated tests.
9. Major architectural changes require an Architecture Decision Record.
10. Documentation must change when system behaviour changes.

## What we will not compromise

- Tenant isolation
- Source grounding
- Clear failure behaviour
- Security of secrets and uploaded data
- Accessibility
- Auditability of important administrative and AI operations
- Maintainable interfaces between platform layers

## Long-term platform layers

```text
Channels and Applications
  Website Widget
  Client Dashboard
  Internal Assistant
  Teams / Slack / WhatsApp / Voice

Conversation and Workflow Layer
  Sessions
  Messages
  Memory
  Tools
  Agents
  Human Handover

AI Core
  RAG Orchestrator
  Prompt Registry
  Model Registry
  Provider Router
  Token and Cost Engine
  Citation Validation
  Evaluation

Knowledge Platform
  Sources
  Versions
  Ingestion
  Chunking
  Embeddings
  Retrieval
  Governance

Platform Foundation
  Tenancy
  Authentication
  RBAC
  Audit
  Observability
  Storage
  Queues
  Deployment
```

## Decision test

Before approving a feature or architectural change, ask:

1. Does it preserve tenant isolation?
2. Is the intelligence source-grounded?
3. Can the capability be reused by another product or channel?
4. Can it be observed, tested, and costed?
5. Does it remain within the approved product phase?
6. Does the user experience follow controlled Expressionism without weakening trust or accessibility?

If a proposal fails these tests, redesign it before implementation.
