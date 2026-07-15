# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-063B1 - Public Message Preparation and Idempotency

## Active Objective

Implement the internal preparation foundation for future public widget messages without exposing a public message route:

- public message contracts
- strict message validation
- persistent idempotency records
- session validation preparation
- atomic message-slot consumption
- lazy conversation creation and attachment
- transaction-state scaffolding

## Current Sources

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/02_Architecture/08_Public_Widget_Message_RAG_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `docs/adr/0013-public-widget-message-rag-boundary.md`
- `planning/tasks/TASK-063B1-public-message-preparation-idempotency.md`

## Guardrails

- Do not implement a public widget message route in TASK-063B1.
- Do not call retrieval, RAG, AI Core, providers, abuse services, moderation, or cost-control services.
- Do not create public message HTTP schemas, streaming, widget SDK/UI, or CORS changes.
- Public clients never choose tenant, conversation, model, provider, prompt, retrieval, context, token limits, or policy overrides.
- Idempotency keys and raw session tokens must never be stored or emitted in plaintext.

## Definition Of Done

- Planning task file exists.
- `public_message_requests` model and migration exist.
- Internal contracts, validation, idempotency repository/service, and preparation service exist.
- Gateway has an internal-only `message_send` preparation extension point.
- Focused validation, idempotency, and preparation tests pass.
- Documentation and `.env.example` are updated.
- `git diff --check` passes.
