# ADR-0011: Public Widget Session Endpoint

Status: Proposed
Date: 2026-07-15

## Context

The Public Access Layer now has internal foundations for public credential persistence, origin validation, distributed rate limiting, and anonymous public sessions. The platform still exposes no public widget runtime route.

The first public endpoint should allow a browser-hosted widget to create an anonymous session before future message sending. The endpoint must preserve tenant isolation, avoid dashboard authentication confusion, require validated Origin, apply rate limits, and return only an opaque bearer session token plus safe session metadata.

The endpoint must not call RAG, create conversations, accept messages, or expose widget configuration internals.

## Decision

Implement the future public widget session endpoint as a thin FastAPI public widget route using the existing Public Access Gateway in `session_creation` mode:

```text
POST /api/v1/widget/{public_key}/sessions
```

The route will:

1. Parse the path parameter, headers, peer IP, and minimal JSON body.
2. Reject dashboard cookies, bearer tokens, development auth headers, and tenant parameters.
3. Use the `widget` channel adapter.
4. Resolve the public widget credential and tenant through the Public Access Gateway.
5. Validate Origin through the existing origin-validation stage.
6. Apply `widget_session_create` rate limits.
7. Create an anonymous public session through the session service.
8. Return an opaque bearer token and safe expiry/capability metadata.

The route will use no cookies. It will rely on explicit bearer session tokens for future message requests. CORS will dynamically allow only the validated configured Origin, with no wildcard Origin and no browser credentials.

## Alternatives Considered

### A. Direct Route Calling Session Service

Pros:

- Faster to implement for one endpoint.
- Fewer adapter layers.

Cons:

- Duplicates tenant, origin, rate-limit, and safe-error logic.
- Increases risk of bypassing Public Access Layer invariants.
- Makes future channels harder to keep consistent.

Rejected.

### B. Route Using Public Access Gateway

Pros:

- Reuses the established public-channel boundary.
- Keeps tenant resolution, origin validation, rate limiting, and session creation ordering consistent.
- Avoids duplicating security logic in route handlers.
- Keeps future channel extraction possible.

Cons:

- Requires a real widget channel adapter and route-to-gateway adaptation.
- Gateway contracts must remain careful not to expose internal IDs.

Chosen.

### C. API Gateway Or External Service Outside FastAPI Immediately

Pros:

- Potentially stronger perimeter controls at scale.
- Could centralise public API policy outside the app.

Cons:

- Premature operational complexity.
- Still needs application-owned tenant, credential, widget configuration, and session state.
- Slower local development and testing.

Rejected for MVP. Future service extraction remains possible.

### D. Cookie-Backed Browser Session Endpoint

Pros:

- Familiar browser session model.
- HttpOnly cookies can reduce JavaScript token exposure in same-site applications.

Cons:

- Third-party iframe/widget deployment is complicated by browser cookie restrictions.
- Requires CSRF design.
- Couples widget storage architecture to API session security too early.

Rejected for MVP.

## Consequences

Positive:

- The first public route stays aligned with the Public Access Layer bounded context.
- Public session creation uses the same security sequence as future public message handling.
- No tenant IDs or conversation IDs are accepted from the browser.
- No RAG or conversation side effects occur during session creation.
- CORS and Origin validation have one decision source.

Trade-offs:

- Bearer-token theft remains a residual risk for future clients, mitigated by Origin binding, expiry, rate limiting, and future iframe storage guidance.
- Session creation retries may create duplicate sessions until idempotency is added.
- Public route implementation requires careful safe-error projection.

## Required Controls

- Use `POST /api/v1/widget/{public_key}/sessions`.
- Require `Origin`.
- Use no cookies.
- Reject dashboard auth and development headers.
- Accept no tenant IDs, message, conversation ID, PII, model/provider/prompt keys, policy overrides, Origin body field, or IP body field.
- Resolve public key server-side to active `widget_public_key`.
- Require active organisation and workspace.
- Require published widget configuration for production session creation.
- Validate Origin before normal credential/workspace rate limits.
- Apply `widget_session_create` rate limits before persistence.
- Return the public session token only once.
- Return no internal session ID, credential ID, tenant IDs, allowed origins, policy internals, token hash, or provider/model details.
- Do not call RAG or create a conversation.

## CORS Decision

The endpoint requires dynamic CORS:

- `OPTIONS` preflight must validate public key and Origin where practical.
- `POST` response should set `Access-Control-Allow-Origin` only to the exact validated Origin.
- Set `Vary: Origin`.
- Allow only `POST`, `OPTIONS`, and explicitly approved headers.
- Do not allow browser credentials.
- Do not use wildcard Origin.
- Safe CORS denials must not expose configured origins.

## Idempotency Decision

MVP defers hard idempotency.

The endpoint may accept bounded `client_request_id` for telemetry and duplicate/retry estimation, but it is not a promise to return the same session. Rate limits constrain duplicate session creation. A future task may add `Idempotency-Key` with server-side dedupe using safe keyed hashes.

## Non-Goals

This ADR does not implement:

- FastAPI route.
- Widget channel adapter.
- Public schemas.
- CORS helper or middleware.
- Public config endpoint.
- Public message endpoint.
- RAG calls.
- Conversation creation.
- Widget SDK/UI.
- New migration.
- Redis changes.

## Related Documents

- `implementation-pack/02_Architecture/06_Public_Widget_Session_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `planning/tasks/TASK-061A-public-widget-session-endpoint-architecture.md`

