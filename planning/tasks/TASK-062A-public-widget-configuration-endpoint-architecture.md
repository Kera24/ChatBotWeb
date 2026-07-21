# TASK-062A - Public Widget Configuration Endpoint Architecture

Status: Complete
Type: Architecture and planning
Sprint: Sprint 3C - Public Channels

## Objective

Design the public read-only widget-configuration endpoint:

```text
GET /api/v1/widget/{public_key}/config
```

The endpoint returns only published, sanitised, public-safe widget configuration. It must not create a session, accept a message, invoke RAG, expose tenant identity, or expose internal policy/provider information.

## Required Reading

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/02_Architecture/06_Public_Widget_Session_Endpoint_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- ADRs 0005 through 0011
- TASK-057A/B, TASK-058A/B, TASK-059A/B, TASK-060A/B, TASK-061A/B
- Public Access, credential/configuration, origin, rate-limit, and public widget session engineering docs
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Architecture Decisions

- Add a dedicated read-only public configuration endpoint instead of returning branding/configuration from session creation.
- Require no request body and no functional query parameters for MVP; HTTP cache validators use headers, not query parameters.
- Route must use the Public Access Gateway with a new `config_read` operation mode.
- Resolve public key server-side to an active `widget_public_key` credential, active organisation, active workspace, and published widget configuration.
- Require validated `Origin` for production and staging config reads, with development localhost support only for development credentials.
- Apply `widget_config_read` rate limits across global, channel, credential, workspace, organisation, and IP dimensions.
- Return a versioned, sanitised response containing only public widget presentation, behaviour, privacy, capability, versioning, and request metadata.
- Exclude tenant IDs, internal credential/config IDs, allowed origins, policy internals, provider/model/prompt details, rate-limit rules, secret/hash fields, audit metadata, and internal asset paths.
- Use platform-controlled public asset URLs or proxy URLs for raster assets as the MVP asset strategy.
- Use ETag, `If-None-Match`, `304 Not Modified`, `Cache-Control`, and `Vary: Origin` as the future HTTP caching contract.
- Map missing, invalid, wrong-type, revoked, expired, disabled, inaccessible, draft, unpublished, or missing configuration to enumeration-resistant public errors.

## Non-Goals

TASK-062A does not implement:

- Public routes.
- Request or response schemas.
- CORS helpers or middleware.
- ETag helpers or caches.
- Asset proxy or upload handling.
- Widget SDK or UI.
- Session creation changes.
- Message endpoint.
- RAG or AI Core calls.
- Conversation persistence.
- Database migrations.

## TASK-062B Implementation Breakdown

Future implementation should be a separate task and include:

1. Public config request/response schemas.
2. Widget adapter config-read support.
3. Thin public route for `GET` and `OPTIONS /api/v1/widget/{public_key}/config`.
4. Public Access Gateway `config_read` mode.
5. Published widget configuration resolver.
6. Public response sanitiser.
7. Asset URL projector.
8. ETag and conditional response helper.
9. Route-scoped dynamic CORS integration.
10. Safe public error mapper.
11. Tests and engineering documentation.

TASK-062B must not combine session creation, message handling, RAG, or widget SDK work.

## Acceptance Criteria

- Endpoint scope is explicitly read-only.
- Gateway usage is mandatory.
- Origin and CORS policy are defined.
- Public response schema and exclusions are complete.
- Published-configuration rules are explicit.
- Cache and ETag strategy is defined.
- Branding and Expressionism safety boundaries are explicit.
- Rate-limit policy is defined.
- Threat and failure models are complete.
- ADR-0012 records the decision.
- No code or route is added.

## Verification

- `git diff --check`
