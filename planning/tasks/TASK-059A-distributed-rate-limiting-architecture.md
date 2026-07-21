# TASK-059A - Distributed Rate Limiting Architecture

## Task ID

TASK-059A

## Linked epic/story

- EPIC-004 - Public Access Layer
- ADR-0005 - Public Widget Security Boundary
- ADR-0006 - Public Access Layer Bounded Context
- ADR-0008 - Origin Validation Policy
- ADR-0009 - Distributed Rate Limiting Policy

## Type

Architecture task. Must be approved before TASK-059B implementation starts.

## Status

Proposed architecture complete.

## Objective

Design the distributed rate-limiting and quota-control subsystem for future public channels.

The design supports 10,000 organisations, multiple API instances, Redis-backed distributed decisions, tenant-level cost protection, and safe degradation when Redis is unavailable.

## Required reading

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
- `planning/tasks/TASK-057B-credential-widget-configuration-implementation.md`
- `planning/tasks/TASK-058A-origin-validation-architecture.md`
- `planning/tasks/TASK-058B-origin-validation-implementation.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `docs/04_Engineering/Origin_Validation.md`
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Deliverables

- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `.ai/CURRENT_SPRINT.md` updated to Sprint 3B / TASK-059A
- `.ai/PROJECT_CONTEXT.md` updated with distributed limiter guardrails

## Scope

Rate limiting owns:

- request-rate enforcement
- burst protection
- sustained-rate limits
- per-IP limits
- per-credential limits
- per-workspace limits
- per-organisation limits
- per-session limits future
- global emergency limits
- daily/monthly quota placeholders
- Retry-After calculation
- stable public errors
- rate-limit decision events
- Redis-backed distributed state
- policy-profile integration

Rate limiting does not own:

- credential resolution
- origin validation
- anonymous session creation
- RAG execution
- provider token accounting
- billing
- permanent analytics
- abuse classification beyond simple counters

## Architecture decisions

- Use Redis-backed atomic token buckets for MVP.
- Compose all applicable dimensions; every applicable limit must pass.
- Use safe Redis keys with environment, dimension, hashed identity, and endpoint category.
- Never put raw public keys, partner secrets, IP addresses, session tokens, message content, or PII in Redis keys.
- Trust forwarded IP headers only from configured trusted proxies.
- Evaluate normal rate limits after credential, tenant, policy, size, and origin validation.
- Allow only a coarse pre-origin global/IP guard for flood absorption if future implementation approves it.
- Fail closed for widget session creation, widget message send, partner API requests, and uncertain global emergency controls.
- Allow constrained fail-open only for selected read-only config reads with a conservative local limiter.
- Keep short-window rate limits separate from daily/monthly quotas.

## Proposed future contracts

`RateLimitRule` should include:

- category
- dimension
- capacity
- refill tokens
- refill period seconds
- request cost
- enabled flag
- fail mode
- priority
- retry-after cap seconds

`RateLimitRequest` should include:

- request ID and trace ID
- channel and category
- credential, organisation, and workspace IDs
- client IP identity
- optional session ID
- policy profile
- request cost
- received timestamp

`RateLimitDecision` should include:

- allowed flag
- reason code
- limiting dimension
- limit
- remaining
- retry-after seconds
- reset timestamp
- safe metadata
- degraded flag

## Gateway order

Planned Public Access Gateway order:

1. Validate request.
2. Resolve channel.
3. Resolve credential.
4. Resolve tenant and policy.
5. Validate message/request size.
6. Validate origin.
7. Apply rate limits.
8. Continue to future session/cost/abuse stages.

Rate denial must prevent anonymous session creation, RAG orchestration, provider execution, and persistence side effects beyond safe operational events.

## Future implementation sequence

1. `TASK-059B` rate-limit contracts and policy models.
2. Redis client foundation.
3. Atomic token-bucket implementation.
4. Trusted IP extraction.
5. Public Access Gateway integration.
6. Local degraded fallback for selected read-only categories.
7. Security, concurrency, and chaos tests.
8. Future quota accounting integration.

## Explicit non-implementation constraint

Do not implement in this task:

- Redis client code.
- Lua scripts.
- Rate-limit middleware.
- Public routes.
- Sessions.
- RAG calls.
- Quota persistence.
- Billing.
- Widget UI.

## Verification

Run:

```bash
git diff --check
```

No automated runtime tests are required because this is planning-only.

## Acceptance criteria

- [x] Algorithm is selected.
- [x] Dimensions and combination rules are explicit.
- [x] Redis key/identity model is safe.
- [x] Proxy/IP trust model is defined.
- [x] Gateway order is clear.
- [x] Failure policies are explicit per category.
- [x] Quota boundary is defined.
- [x] Threat model and diagrams are complete.
- [x] ADR records the decision.
- [x] No runtime code is added.
