# ADR-0010: Anonymous Public Session Security

Status: Proposed
Date: 2026-07-15

## Context

The Public Access Layer separates future public and external channels from authenticated dashboard APIs, internal development APIs, and the RAG Orchestrator. Previous decisions established public credential boundaries, credential storage, origin validation, and Redis-backed rate limiting.

Future widget and browser-based channels need anonymous sessions so a browser can continue a conversation without submitting trusted tenant IDs or raw conversation IDs. The session mechanism must work across horizontally scaled API instances, support immediate revocation, preserve tenant isolation, and avoid leaking secrets or internal identifiers.

## Decision

Use opaque random public bearer tokens with a public token ID plus high-entropy secret material:

```text
pss_<environment>_<token_id>.<secret>
```

The browser receives the full token once at session creation. The server stores:

- `public_token_id` for indexed lookup.
- `token_secret_hash` for verification.
- Tenant, credential, channel, environment, policy, origin, lifecycle, expiry, and conversation binding fields.

The secret hash is computed with a keyed HMAC or equivalent keyed digest over token version, token ID, and secret material. Verification uses constant-time comparison. Full tokens and token secrets are never stored in plaintext, returned after creation, logged, or included in audit events.

PostgreSQL is the source of truth for public sessions. Redis may later cache safe projections, but revocation, lifecycle, and tenant binding rely on durable database state.

Widget message requests must validate a credential-bound session after credential resolution, tenant resolution, request validation, origin validation, and rate limiting. The browser must not submit a trusted conversation ID. Existing tenant-scoped conversations are lazily attached to the session on the first accepted message.

## Alternatives Considered

### A. Store full random token hash and query by hash

This is simple and avoids a public token ID, but every lookup requires hashing the whole presented token before querying. It makes observability and revocation workflows less ergonomic because there is no safe token handle to reference. It was not selected.

### B. Public token ID plus secret hash

This separates lookup from proof of possession. The token ID is safe enough for operational references, while the secret remains bearer material. It supports indexed lookup, constant-time secret verification, revocation, and future key rotation. This is selected.

### C. Signed self-contained token

A signed token reduces database reads but makes revocation, tenant binding updates, credential disablement, and policy changes harder to enforce immediately. It also increases the risk of accidentally trusting embedded tenant claims. It was rejected for MVP.

### D. Encrypted stateless token

Encrypted tokens hide claims from the browser, but still carry revocation and policy-staleness problems. They add key-management complexity without improving tenant isolation enough for MVP. They were rejected.

### E. Cookie-backed server session

Cookies complicate third-party iframe/widget deployment because of SameSite and third-party cookie restrictions. They also couple browser storage policy to the API security model. This was rejected for the public widget MVP.

## Consequences

Positive consequences:

- Immediate session revocation is possible.
- Tenant, credential, origin, and channel binding are verified server-side.
- Public tokens contain no trusted tenant IDs.
- Session records support lifecycle, expiry, message caps, and operational visibility.
- Lazy conversation attachment avoids empty conversations from unused sessions.

Trade-offs:

- Each validation needs a database lookup unless a future cache is added.
- Bearer-token theft remains a residual risk until mitigated by origin binding, expiry, rate limiting, and future replay controls.
- Cleanup and archival jobs are needed as session volume grows.
- Concurrency control is required for first-message conversation attachment and message-count increments.

## Required Controls

- Generate high-entropy URL-safe token IDs and secrets.
- Store no raw session token or secret in the database.
- Use keyed hashing and constant-time comparison.
- Bind each session to credential, organisation, workspace, channel, environment, policy profile, and validated origin.
- Re-check credential, organisation, workspace, session status, expiry, and origin binding on every session use.
- Fail closed for invalid, expired, revoked, blocked, or mismatched sessions.
- Never expose internal session IDs, token hashes, configured origins, or tenant IDs in public errors.
- Do not create conversations until the first accepted message.
- Use row locking or atomic compare-and-set for first conversation attachment and message-count updates.

## Browser Storage Guidance

For the future iframe/widget MVP, store the public session token in `sessionStorage` inside the widget frame. This survives refresh within the tab without long-lived persistence. A stricter in-memory mode may be offered for sensitive clients. Avoid `localStorage` by default because host-site XSS can persistently exfiltrate bearer material. Avoid cookie-backed sessions for MVP due to third-party cookie constraints.

## Non-Goals

This ADR does not implement:

- SQLAlchemy models
- Alembic migrations
- token generation or hashing code
- session repository/service
- gateway session validation stage
- public session endpoint
- Redis session cache
- widget code
- RAG calls
- cleanup jobs
- CORS changes

## Related Documents

- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
