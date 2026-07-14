# Distributed Rate Limiting

Status: Implemented foundation. No public endpoint, session flow, quota persistence, billing, widget runtime, CORS middleware, or RAG call exists.

## Module Layout

TASK-059B adds `apps/api/app/access/rate_limit`:

- `contracts.py` defines `RateLimitRule`, `RateLimitRequest`, and `RateLimitDecision`.
- `policies.py` defines default rule sets for internal test, planned widget, and planned partner API profiles.
- `identities.py` builds HMAC identities and safe Redis keys.
- `client_ip.py` extracts trusted client IP identities.
- `token_bucket.py` contains deterministic token-bucket math and script result parsing.
- `redis_store.py` contains the Redis store wrapper, Lua script, Redis client factory, and test in-memory store.
- `local_fallback.py` contains a conservative per-process fallback limiter.
- `service.py` evaluates multi-dimensional rules, failure modes, local fallback, emergency controls, safe events, and safe public errors.

## Algorithm

The foundation uses Redis-backed atomic token buckets. Each rule has:

- capacity
- refill tokens
- refill period
- request cost
- fail mode
- priority
- retry-after cap

`token_bucket_v1` performs refill and consume as one Redis Lua operation. Unit tests use `InMemoryRateLimitStore` so normal API tests do not require Redis.

## Policy Integration

`AccessPolicyProfile` now carries `rate_limit_rules`. Existing policy behaviour is preserved because rules are explicit and evaluated only when a `RateLimitService` is injected into the gateway.

Default profiles include planned rules for:

- `internal_test`
- `widget_config_read`
- `widget_session_create`
- `widget_message_send`
- `partner_api_request`

## Dimensions

Supported dimensions:

- global
- channel
- credential
- workspace
- organisation
- IP
- session
- endpoint category

All enabled applicable rules for a category must pass. Rules are evaluated deterministically by priority then rule key.

## Redis Keys And Identity Hashing

Key format:

```text
rate:{environment}:{dimension}:{hashed_identity}:{category}
```

Identities use keyed HMAC with `RATE_LIMIT_IDENTITY_SECRET`. Redis keys do not contain raw public identifiers, partner secrets, IP addresses, session tokens, tenant names, message content, or PII.

Configuration placeholders:

- `RATE_LIMIT_IDENTITY_SECRET`
- `RATE_LIMIT_REDIS_PREFIX`
- `RATE_LIMIT_REDIS_TIMEOUT_SECONDS`
- `RATE_LIMIT_LOCAL_FALLBACK_ENABLED`
- `TRUSTED_PROXY_NETWORKS`

The `.env.example` values are development placeholders only.

## Trusted IP Extraction

`client_ip.py` uses the direct socket peer address by default. `X-Forwarded-For` and `X-Real-IP` are trusted only when the immediate peer is in configured trusted proxy networks.

The extraction strategy parses `X-Forwarded-For` from right to left and selects the first untrusted hop. Malformed trusted-proxy chains raise a safe validation error for callers to handle.

## Failure Modes

Sensitive categories fail closed when Redis is unavailable or times out:

- `widget_message_send`
- `widget_session_create`
- `partner_api_request`

`widget_config_read` can use local degraded fallback only when explicitly enabled and only under a rule fail mode that permits it.

Local fallback is:

- per-process only
- conservative
- short-lived
- explicit and injectable
- marked degraded in decisions/events
- not used for message/session or partner API protection

## Gateway Integration

`PublicAccessGateway` accepts an optional injected `RateLimitService`. When injected, the flow is:

1. Validate request.
2. Resolve channel.
3. Resolve credential.
4. Resolve tenant and policy.
5. Validate request/message size.
6. Validate Origin when configured.
7. Apply rate limits.
8. Return validated context.

The gateway still stops before anonymous sessions, abuse detection, cost enforcement, RAG orchestration, and public response generation.

## Safe Errors And Events

Denied requests map to existing public-safe errors:

- `rate_limited`
- `temporarily_unavailable`
- `safe_internal_error` future fallback

Events added:

- `rate_limit.allowed`
- `rate_limit.denied`
- `rate_limit.redis_unavailable`
- `rate_limit.redis_timeout`
- `rate_limit.degraded_local_fallback`
- `rate_limit.invalid_policy`
- `rate_limit.emergency_mode`

Events do not include raw IPs, public keys, secrets, Redis keys, or message content.

## Operational Header Contract

Future route adapters may project decision metadata into:

- `Retry-After`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

Detailed multi-dimensional policy internals must not be exposed to public widget callers.

## Tests

Focused tests:

```bash
cd apps/api
python -m pytest tests/test_rate_limit.py
```

Full verification:

```bash
npm run api:test
npm run verify
```

## Warnings

No public route uses this foundation yet. Future public config/session/message endpoints must explicitly inject and enforce `RateLimitService`; no public message/session endpoint may bypass it.
