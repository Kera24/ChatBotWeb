# ADR-0012: Public Widget Configuration Delivery

Status: Proposed
Date: 2026-07-15

## Context

The platform now has public access foundations, public widget credentials/configuration, origin validation, distributed rate limiting, anonymous public sessions, and a public widget session-creation endpoint. A browser widget also needs public branding and behaviour configuration before it creates a session or sends a message.

Serving configuration through session creation would force browsers to create server-side state just to render the widget. The platform needs a read-only endpoint that returns only published, sanitised, public-safe configuration while preserving the Public Access Layer boundary.

The endpoint must not create sessions or conversations, accept messages, call retrieval, invoke RAG, expose tenant identity, expose allowed origins, or reveal provider/model/prompt/policy internals.

## Decision

Use a dedicated read-only public configuration endpoint through the Public Access Gateway:

```text
GET /api/v1/widget/{public_key}/config
OPTIONS /api/v1/widget/{public_key}/config
```

The route will use a future `config_read` gateway mode. It will resolve the public widget credential and tenant server-side, require a validated Origin, apply `widget_config_read` rate limits, load only published widget configuration, sanitise the response, and return versioned public configuration with dynamic CORS and ETag support.

The endpoint uses no cookies and returns no session token. It does not create a session, conversation, chat message, retrieval request, RAG request, or AI Core request.

## Alternatives Considered

### A. Serve Config Only In Session-Creation Response

Pros:

- One fewer public endpoint.
- Session and config eligibility can share one request path.

Cons:

- Creates unnecessary sessions for visitors who only open or preload the widget.
- Makes branding and cache behaviour depend on session lifecycle.
- Increases duplicate session pressure during browser retries.
- Prevents cheap 304 config checks.

Rejected.

### B. Dedicated Public Config Endpoint

Pros:

- Separates branding/configuration from session lifecycle.
- Allows preloading and cache validation before session creation.
- Keeps the session endpoint minimal.
- Supports future widget SDK startup flow.
- Still reuses Public Access Gateway credential, origin, rate-limit, and safe-error controls.

Cons:

- Adds CORS/cache complexity.
- Requires careful sanitisation and asset URL projection.
- Published config becomes intentionally public to validated origins.

Chosen.

### C. Embed All Config Into A Generated Script

Pros:

- One browser asset can bootstrap the widget.
- CDN-friendly for static embed scripts.

Cons:

- Mixes executable code and tenant-controlled configuration.
- Harder to invalidate safely after credential revoke or origin changes.
- Increases XSS and cache-confusion blast radius.

Rejected for MVP.

### D. Static CDN Configuration Artifact

Pros:

- Highly cacheable and cheap to serve.
- Good future option for large scale.

Cons:

- Harder to apply live Origin validation.
- Revocation and publish invalidation need a mature asset pipeline.
- Risk of stale config after disable/revoke.

Deferred.

## Consequences

Positive:

- Widgets can render public-safe branding without creating anonymous sessions.
- Session creation remains focused on issuing opaque bearer tokens.
- Public configuration can use ETag and short-lived cache behaviour.
- Gateway-controlled credential, tenant, origin, rate-limit, and safe-error logic stays consistent.
- Draft configuration is never public.

Trade-offs:

- The endpoint adds public surface area that must be covered by Origin validation and rate limits.
- Dynamic CORS and CDN caching require `Vary: Origin` discipline.
- Sanitisation and asset URL projection become security-critical.
- A one-row draft/published model may not support seamless draft editing plus stable public reads without future published snapshots.

## Required Controls

- Use Public Access Gateway `config_read` mode.
- Require validated Origin for production/staging widget config reads.
- Apply `widget_config_read` rate limits.
- Return only published, sanitised configuration.
- Do not expose tenant IDs, internal credential/config IDs, allowed origins, policy internals, provider/model/prompt details, rate-limit rules, internal asset paths, audit metadata, or secrets.
- Use dynamic CORS with no wildcard Origin and browser credentials disabled.
- Use ETag values that do not leak tenant or internal identifiers.
- Use `Vary: Origin`.
- Use safe enumeration-resistant public errors.
- Use platform-controlled public asset URLs or proxy URLs for raster assets.

## Caching Decision

The endpoint should support ETag and `If-None-Match`. `304 Not Modified` is returned only after credential, Origin, and rate-limit checks pass. Browser/CDN cache headers should use short TTLs and include `Vary: Origin`. Errors should use no-store or short negative caching.

Server-side caching may be added later as a short-lived credential/config projection with invalidation on publish, credential disable/revoke/delete, and origin policy change. Revocation uncertainty fails closed.

## Asset Decision

MVP architecture uses platform-controlled public asset URLs or proxy URLs for logo/avatar fields. Production URLs must be HTTPS and restricted to safe raster MIME types. Internal filesystem paths and unsanitised SVG are not public.

## Non-Goals

This ADR does not implement:

- Public route.
- Public schemas.
- CORS code.
- ETag helper or cache.
- Asset proxy.
- Widget SDK/UI.
- Session changes.
- Message endpoint.
- RAG or AI Core calls.
- Conversation creation.
- Migration.

## Related Documents

- `implementation-pack/02_Architecture/07_Public_Widget_Configuration_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/06_Public_Widget_Session_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0011-public-widget-session-endpoint.md`
- `planning/tasks/TASK-062A-public-widget-configuration-endpoint-architecture.md`
