# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-062B - Public Widget Configuration Endpoint Implementation

## Active Objective

Implement the public read-only widget configuration endpoint:

```text
GET /api/v1/widget/{public_key}/config
OPTIONS /api/v1/widget/{public_key}/config
```

The endpoint returns only published, sanitised, public-safe widget configuration through the Public Access Gateway. It must not create sessions or conversations, accept messages, invoke retrieval, invoke RAG, or expose tenant identity or internal provider/policy details.

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
- `docs/adr/0012-public-widget-configuration-delivery.md`
- `planning/tasks/TASK-062B-public-widget-configuration-endpoint-implementation.md`
- `docs/04_Engineering/Public_Widget_Configuration_Endpoint.md`

## Guardrails

- Do not implement public widget message endpoints, RAG, conversations/messages, widget SDK/UI, asset upload/proxy streaming, Redis configuration cache, CDN integration, lead capture, analytics, provider/model exposure, arbitrary CSS/HTML/JavaScript, or global CORS wildcard in TASK-062B.
- Public widget configuration is delivered separately from session creation.
- Config reads must not create sessions or conversations.
- Only published, sanitised configuration is public.
- Draft configuration is never publicly visible.
- Public configuration must pass Origin validation and `widget_config_read` rate limiting.
- Public routes must remain separate from dashboard and internal AI routes.
- No public route may accept tenant IDs, workspace IDs, credential IDs, dashboard bearer tokens, or development auth headers.

## Definition Of Done

- `GET /api/v1/widget/{public_key}/config` exists.
- Route-scoped `OPTIONS /api/v1/widget/{public_key}/config` exists.
- Gateway `config_read` mode is wired.
- Published configuration is projected through a sanitiser, not directly serialised.
- Dynamic CORS, ETag, conditional GET, cache headers, safe errors, events, and tests are implemented.
- Existing public session behavior remains intact.
- Requested verification commands are run or blockers are reported.
