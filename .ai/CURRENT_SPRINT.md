# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-063A - Public Widget Message and RAG Security Architecture

## Active Objective

Design the first public widget message endpoint architecture:

```text
POST /api/v1/widget/{public_key}/messages
```

This is architecture and planning only. The endpoint must require a validated credential-bound anonymous public session, run through the Public Access Gateway before RAG, apply message rate limits, abuse and cost controls, consume a session message slot immediately before expensive RAG processing, attach/reuse a server-owned conversation, call RAG only through a public adapter, and return only sanitised public answer/citation fields.

## Current Sources

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/02_Architecture/06_Public_Widget_Session_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/07_Public_Widget_Configuration_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/08_Public_Widget_Message_RAG_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/03_AI/03_AI_Core_Architecture.md`
- `implementation-pack/03_AI/01_RAG_Implementation_Standards.md`
- `docs/adr/0004-rag-orchestrator-boundary.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `docs/adr/0011-public-widget-session-endpoint.md`
- `docs/adr/0012-public-widget-configuration-delivery.md`
- `docs/adr/0013-public-widget-message-rag-boundary.md`
- `planning/tasks/TASK-063A-public-widget-message-rag-security-architecture.md`

## Guardrails

- Do not implement public message routes, schemas, session validation wiring, RAG calls, abuse controls, cost controls, streaming, widget UI, or migrations in TASK-063A.
- Public messages require a validated credential-bound anonymous session.
- Public clients never choose tenant, conversation, model, provider, prompt, retrieval, context, output, or token limits.
- Public message processing uses Public Access Gateway before the RAG Orchestrator.
- Message slots are consumed immediately before expensive RAG processing.
- Public AI output and citations require a dedicated sanitisation boundary.
- No public message route may be added before TASK-063A approval and a later implementation task.

## Definition Of Done

- Planning task file exists.
- Architecture pack file exists.
- ADR-0013 exists and records the boundary decision.
- Endpoint/request boundary is explicit.
- Gateway and session-validation flow is defined.
- Message-slot decision is documented.
- Conversation attachment and idempotency are defined.
- Abuse controls and cost ceilings are defined.
- RAG adapter and response sanitisation boundaries are defined.
- Transaction/failure policy, CORS, rate limits, threat model, diagrams, and implementation split are documented.
- `git diff --check` passes.
