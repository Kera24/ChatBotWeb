# ADR-0009: Distributed Rate Limiting Policy

Status: Proposed
Date: 2026-07-15

## Context

The Public Access Layer now defines credential resolution and origin validation foundations for future browser and external channels. Before public widget message/session endpoints or partner APIs are exposed, the platform needs distributed rate limiting that works across multiple API instances and protects tenants, providers, and platform cost.

In-process limits are insufficient for horizontally scaled public traffic. Database counters are too slow and contentious for short-window request control. The platform already plans Redis for public abuse controls and background infrastructure.

## Decision

Use Redis-backed atomic token buckets with explicit multi-dimensional policies and conservative local degraded fallback for selected read-only operations.

Chosen policy:

- All applicable dimensions must pass: global, channel, credential, workspace, organisation, IP, and future session/cost buckets.
- Use Redis Lua or equivalent atomic transaction-safe logic for token refill and consumption.
- Use safe Redis keys with environment, dimension, hashed identity, and category.
- Do not store raw public keys, partner secrets, IP addresses, session tokens, or message content in Redis keys.
- Trust forwarded client-IP headers only from configured trusted proxies.
- Widget session creation and message send fail closed on Redis uncertainty.
- Partner API requests fail closed on Redis uncertainty.
- Widget config reads may use constrained fail-open only with a conservative local limiter and safe cached/static response rules.
- Global emergency controls fail closed when state is uncertain.

## Alternatives Considered

### Option A: In-process limiter

Pros:

- Simple and fast.
- No external dependency.

Cons:

- Does not work across multiple API instances.
- Easy to bypass by distributing traffic.
- Loses state on restart.

Rejected as the primary mechanism. Retained only as a constrained degraded fallback for selected read-only operations.

### Option B: Database counters

Pros:

- Durable and familiar.
- Easy to inspect.

Cons:

- Too much write contention for high-volume short-window controls.
- Poor latency for every public request.
- Harder to expire high-cardinality IP/session keys cleanly.

Rejected for request-rate enforcement. Durable accounting may later support quota reconciliation.

### Option C: Redis fixed window

Pros:

- Easy to implement.
- Cheap counters and TTLs.

Cons:

- Boundary bursts allow double spending near window edges.
- Less fair for public chat and expensive AI requests.

Rejected for MVP public message/session controls.

### Option D: Redis sliding window

Pros:

- More accurate than fixed windows.
- Good fairness.

Cons:

- Sliding log is memory-heavy at high scale.
- Sliding counter adds complexity without clear benefit over token bucket for MVP.

Deferred.

### Option E: Redis token bucket

Pros:

- Natural burst and sustained-rate model.
- Efficient state.
- Can be implemented atomically.
- Produces useful retry-after estimates.

Cons:

- Requires careful Lua/script testing.
- Multi-dimensional decisions need clear semantics.
- Redis becomes an operational dependency.

Chosen.

## Consequences

Positive:

- Distributed decisions are consistent across API instances.
- Burst and sustained traffic can be controlled independently.
- Tenant, credential, IP, and global protections compose cleanly.
- Retry-After can be calculated deterministically.
- Future quota integration has a clear boundary.

Trade-offs:

- Redis availability becomes critical for public write and cost-bearing paths.
- Lua/script versioning and concurrency testing are required.
- Redis Cluster support needs key-slot strategy.
- Fail-open behaviour must stay narrow and auditable.

## Required Controls

- Safe key derivation with no raw public keys, secrets, IPs, tokens, or message content.
- Trusted proxy configuration before using forwarded IP headers.
- Category-specific fail policies.
- Safe public errors.
- Safe operational events and metrics.
- Emergency kill switches and reduced-limit modes.
- Tests for concurrency, Redis failure, and cross-tenant isolation.

## Non-Goals

This ADR does not implement:

- Redis client code.
- Lua scripts.
- Rate-limit middleware.
- Public routes.
- Anonymous sessions.
- RAG calls.
- Quota persistence.
- Billing.
- Widget UI.

## Related Documents

- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0008-origin-validation-policy.md`
- `planning/tasks/TASK-059A-distributed-rate-limiting-architecture.md`
