# ADR-0008: Origin Validation Policy

Status: Proposed
Date: 2026-07-15

## Context

The Public Access Layer separates public and external-channel traffic from dashboard APIs. TASK-057B adds persistent public credentials and normalised allowed-origin records, but it intentionally does not validate runtime request origins.

Future browser-based channels, especially the website widget, need a strict origin policy before public session, message, or configuration endpoints are exposed. The policy must prevent accidental tenant exposure, reduce abusive embedding, and remain compatible with local development.

Origin validation is not authentication. Browser headers can be spoofed outside browser contexts, so origin validation must work alongside server-side credential resolution, session validation, rate limiting, cost controls, and tenant-scoped RAG.

## Decision

Adopt a strict browser-origin validation policy:

- `Origin` is required for widget session and message endpoints.
- Missing `Origin` fails closed for widget session and message endpoints.
- `Referer` fallback is disabled for state-changing widget endpoints.
- Public configuration GET may use a policy-gated `Referer` fallback only when explicitly approved for that endpoint and credential policy.
- Partner API credentials bypass browser-origin validation and use separate secret authentication rules.
- Matching checks exact origin first, then tightly controlled one-label subdomain wildcard matching.
- Production widget origins require HTTPS by default.
- Localhost and loopback origins are allowed only for development credentials when explicitly configured.
- Public suffix wildcards, global wildcards, wildcard localhost, and wildcard IPs are rejected.
- Security-sensitive uncertainty fails closed.

The origin validator must use resolved credential and policy context. It must never trust client-supplied organisation IDs, workspace IDs, `Host`, or forwarded headers as tenant identity.

## Alternatives Considered

### Option A: Origin only, no Referer fallback

Pros:

- Simple and strict.
- Avoids privacy and spoofing limitations of `Referer`.
- Easy to reason about for state-changing endpoints.

Cons:

- May block some safe public configuration reads from legacy or constrained browser environments.

Partially chosen. This is the rule for widget session and message endpoints.

### Option B: Origin plus Referer fallback

Pros:

- More compatible with edge browser and static asset contexts.
- Can help configuration GET work where `Origin` is omitted.

Cons:

- `Referer` is privacy-sensitive, inconsistently present, and spoofable outside browsers.
- Easy to overuse and weaken state-changing endpoints.

Accepted only as a policy-gated option for non-state-changing config GET. Rejected for session and message endpoints.

### Option C: Browser token or challenge instead of origin

Pros:

- Can provide stronger proof of runtime widget bootstrap.
- Useful for future anti-abuse and iframe flows.

Cons:

- Requires additional session or challenge infrastructure.
- Does not replace origin allow-list checks.
- Adds complexity before public endpoints exist.

Deferred. It may be added later with anonymous session architecture.

### Option D: No origin validation, rate limiting only

Pros:

- Simple to implement.
- Avoids header edge cases.

Cons:

- Allows any website to embed or call widget endpoints with a public key.
- Increases abuse, tenant confusion, scraping, and denial-of-wallet risk.
- Violates the public widget security boundary.

Rejected.

## Consequences

Positive:

- Widget state-changing endpoints have a clear fail-closed browser-origin policy.
- Public configuration reads can support limited compatibility without weakening message/session endpoints.
- The policy aligns with normalised `credential_allowed_origins` records.
- CORS can consume the same validation result rather than duplicating matching logic.
- Future channels can choose browser-origin enforcement only when appropriate.

Trade-offs:

- Some legitimate browser environments with missing `Origin` will be rejected.
- Public configuration GET requires careful endpoint-specific policy if compatibility fallback is needed.
- Origin validation cannot stop server-to-server spoofing by itself.
- Cache invalidation and fail-closed database/cache behaviour must be implemented carefully.

## Required Controls

- Resolve public credential before origin validation.
- Load allowed origins only for the resolved credential and environment.
- Match exact origins before wildcard origins.
- Reject malformed, unsupported, insecure, or environment-incompatible origins.
- Emit safe security events for allowed, denied, malformed, missing, wildcard, and cache-failure decisions.
- Do not log full raw headers by default.
- Do not expose configured allowed-origin lists in public errors.
- Add `Vary: Origin` when CORS responses are later implemented.

## Non-Goals

This ADR does not implement:

- Python origin matcher code.
- Middleware.
- CORS configuration.
- Database migrations.
- Public routes.
- Redis caching.
- Anonymous sessions.
- Widget UI.
- DNS ownership verification.

## Related Documents

- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `planning/tasks/TASK-058A-origin-validation-architecture.md`
