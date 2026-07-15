# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-062A - Public Widget Configuration Endpoint Architecture

## Active Objective

Design the public read-only widget configuration endpoint:

```text
GET /api/v1/widget/{public_key}/config
```

This is architecture and planning only. The endpoint will return published, sanitised, public-safe widget configuration through the Public Access Gateway. It must not create sessions or conversations, accept messages, invoke retrieval, invoke RAG, or expose tenant identity or internal provider/policy details.

## Current Sources

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/02_Architecture/06_Public_Widget_Session_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/07_Public_Widget_Configuration_Endpoint_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `docs/adr/0011-public-widget-session-endpoint.md`
- `docs/adr/0012-public-widget-configuration-delivery.md`
- `planning/tasks/TASK-062A-public-widget-configuration-endpoint-architecture.md`

## Guardrails

- Do not implement public routes, schemas, CORS code, caches, widget SDK/UI, sessions, messages, RAG, or migrations in TASK-062A.
- Public widget configuration is delivered separately from session creation.
- Config reads must not create sessions or conversations.
- Only published, sanitised configuration is public.
- Draft configuration is never publicly visible.
- Public configuration must pass Origin validation and `widget_config_read` rate limiting.
- Public routes must remain separate from dashboard and internal AI routes.
- No public route may accept tenant IDs, workspace IDs, credential IDs, dashboard bearer tokens, or development auth headers.

## Definition Of Done

- Planning task file exists.
- Architecture pack file exists.
- ADR-0012 exists and records the delivery decision.
- Endpoint boundary is read-only and explicit.
- Gateway usage is mandatory.
- Origin/CORS policy is defined.
- Published-config eligibility is defined.
- Response schema, exclusions, asset strategy, cache/ETag strategy, rate-limit behaviour, safe errors, threat model, failure matrix, and diagrams are documented.
- `git diff --check` passes.
