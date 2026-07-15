# TASK-061A: Public Widget Session Endpoint Architecture

Status: Complete
Type: Architecture task
Sprint: Sprint 3C - Public Channels

## Objective

Design the first publicly exposed endpoint for the platform:

```text
POST /api/v1/widget/{public_key}/sessions
```

This endpoint creates an anonymous public session only. It must not call RAG, create a conversation, accept a message, expose widget configuration details beyond safe session capabilities, or reuse dashboard/internal behaviour.

## Required Reading

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057B-credential-widget-configuration-implementation.md`
- `planning/tasks/TASK-058B-origin-validation-implementation.md`
- `planning/tasks/TASK-059B-distributed-rate-limiting-implementation.md`
- `planning/tasks/TASK-060A-anonymous-public-session-architecture.md`
- `planning/tasks/TASK-060B-anonymous-public-session-implementation.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `docs/04_Engineering/Origin_Validation.md`
- `docs/04_Engineering/Distributed_Rate_Limiting.md`
- `docs/04_Engineering/Anonymous_Public_Sessions.md`
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Deliverables

- `implementation-pack/02_Architecture/06_Public_Widget_Session_Endpoint_Architecture.md`
- `docs/adr/0011-public-widget-session-endpoint.md`
- `planning/tasks/TASK-061A-public-widget-session-endpoint-architecture.md`
- `.ai/CURRENT_SPRINT.md` updated to Sprint 3C / TASK-061A
- `.ai/PROJECT_CONTEXT.md` updated with public widget session endpoint guardrails

## Architecture Decision Summary

- The first public endpoint is `POST /api/v1/widget/{public_key}/sessions`.
- The route must be a thin FastAPI public-widget adapter that calls the existing Public Access Gateway in `session_creation` mode.
- Public routes must be visibly separate from authenticated dashboard routes, internal AI/RAG routes, and development-only paths.
- The request body should be empty or nearly empty; no message, tenant ID, conversation ID, PII, model, provider, prompt, policy override, Origin, or client IP is accepted from the body.
- `Origin` is required from HTTP headers and must be validated before session creation.
- `widget_session_create` rate limits must run before session persistence.
- Session creation returns an opaque bearer session token once and safe capability/expiry metadata only.
- The endpoint must not create a conversation, call retrieval, call AI Core, or create chat messages.
- CORS must be dynamic and consume the validated Origin decision; no wildcard CORS and no credentials.
- MVP idempotency is deferred; session creation is protected by rate limits and may later add `Idempotency-Key` or bounded `client_request_id`.

## Explicit Non-Goals

Do not implement in TASK-061A:

- FastAPI public route.
- Widget channel adapter.
- Public schemas.
- CORS helper or middleware.
- RAG invocation.
- Conversation creation.
- Public config endpoint.
- Public message endpoint.
- Widget SDK/UI.
- New migration.
- Redis changes.
- Runtime code changes.

## Future Implementation Breakdown

TASK-061B should implement only:

1. `widget` channel adapter.
2. Public request/response schemas.
3. Thin public session route.
4. Dynamic CORS helper specific to validated Origin.
5. Gateway `session_creation` wiring.
6. Safe public error mapper.
7. Tests for routing, security, origin, rate limit, sessions, privacy, reliability, and no-RAG behaviour.
8. Documentation updates.

TASK-061B must not combine public message/RAG endpoint work.

## Acceptance Criteria

- [x] Endpoint boundary is explicit.
- [x] Request contract is minimal.
- [x] Tenant, conversation, and message input are forbidden.
- [x] Public Access Gateway usage is mandatory.
- [x] CORS policy is defined.
- [x] Safe response and error contracts are complete.
- [x] Credential, widget configuration, and session dependencies are defined.
- [x] Threat and failure models are complete.
- [x] ADR-0011 records the route design.
- [x] No code, migration, public route, schemas, CORS middleware, widget SDK/UI, conversation creation, or RAG call is added.

## Verification

Run:

```bash
git diff --check
```

