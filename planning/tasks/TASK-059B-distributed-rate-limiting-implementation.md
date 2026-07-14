# TASK-059B - Distributed Rate Limiting Implementation

## Task ID

TASK-059B

## Linked architecture

- `planning/tasks/TASK-059A-distributed-rate-limiting-architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`

## Type

Implementation task.

## Status

Implemented.

## Objective

Implement the distributed rate-limiting foundation using Redis-backed atomic token buckets, trusted client-IP extraction, explicit failure policies, and Public Access Gateway integration.

No public widget endpoint, quota persistence, anonymous session, RAG call, billing, CORS middleware, or widget UI is implemented by this task.

## Implemented scope

- Rate-limit package under `apps/api/app/access/rate_limit`.
- Rate-limit contracts and serialisable decisions.
- Access policy integration with default rule sets.
- Safe HMAC identity and Redis key generation.
- Trusted client-IP extraction.
- Redis client factory and token-bucket Lua script wrapper.
- In-memory test store.
- Conservative local degraded fallback limiter.
- Multi-dimensional rule evaluation.
- Redis timeout/unavailable failure policies.
- Emergency-control placeholders.
- Optional Public Access Gateway rate-limit stage.
- Safe events and safe public error mapping.
- Focused unit and gateway tests.

## Explicitly not implemented

- Public routes.
- Widget config endpoint.
- Widget session endpoint.
- Widget message endpoint.
- Anonymous sessions.
- Quotas.
- Billing.
- Public analytics.
- Abuse classifier.
- RAG calls.
- Widget SDK/UI.
- CORS middleware.
- Domain ownership verification.

## Verification

Required commands:

```bash
docker compose up -d redis
npm run api:test
npm run verify
git diff --check
```

Focused command:

```bash
cd apps/api
python -m pytest tests/test_rate_limit.py
```

## Acceptance criteria

- [x] Rate-limit contracts exist.
- [x] Policy profiles can declare validated rules.
- [x] Redis client foundation exists without hidden global client.
- [x] Token-bucket logic supports refill, capacity caps, request costs greater than one, retry-after, and TTL.
- [x] Redis key identities are HMAC-derived and safe.
- [x] Trusted IP extraction rejects arbitrary forwarded-header trust.
- [x] Multi-dimensional evaluation requires all rules to pass.
- [x] Sensitive Redis failures fail closed.
- [x] Local fallback is constrained and explicit.
- [x] Gateway can invoke rate limiting after origin validation.
- [x] Safe errors and events are emitted.
- [x] No public endpoint is added.
