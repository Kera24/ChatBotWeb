# TASK-058B - Origin Validation Implementation

## Task ID

TASK-058B

## Linked architecture

- `planning/tasks/TASK-058A-origin-validation-architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `docs/adr/0008-origin-validation-policy.md`

## Type

Implementation task.

## Status

Implemented.

## Objective

Implement origin normalisation, exact/wildcard matching, credential-scoped origin lookup, and Public Access Gateway integration.

No public widget endpoint, CORS middleware, Redis cache, anonymous session, rate limiter, widget SDK/UI, RAG call, or partner API authentication is implemented by this task.

## Implemented scope

- Origin-validation package under `apps/api/app/access/origin_validation`.
- Typed origin validation request/result contracts.
- Strict origin normalisation and canonical serialisation.
- Exact matching and one-label wildcard matching.
- Environment restrictions for development, staging, and production.
- Missing-Origin policy for widget, partner API, and internal test policies.
- Credential-scoped repository reads from `credential_allowed_origins`.
- Defensive service-level filtering by credential ID.
- Safe public origin errors.
- Safe origin validation events.
- Optional Public Access Gateway integration through injected `OriginValidationService`.
- Focused tests for normalisation, matching, service behaviour, repository scope, and gateway integration.

## Explicitly not implemented

- Public widget endpoints.
- Public widget configuration endpoint.
- CORS middleware.
- Redis cache.
- Rate limiting.
- Anonymous sessions.
- DNS ownership verification.
- Referer fallback for state-changing requests.
- Widget SDK/UI.
- RAG calls.
- Partner API authentication.
- Browser fingerprinting.

## Verification

Required commands:

```bash
npm run api:test
npm run verify
```

Focused commands:

```bash
cd apps/api
python -m pytest tests/test_origin_validation.py
python -m pytest tests/test_public_access_layer.py
```

No migration is added for TASK-058B.

## Acceptance criteria

- [x] Origin normalisation handles safe host, port, IDN, IP, IPv6, localhost, and loopback cases.
- [x] Unsafe paths, query strings, fragments, userinfo, malformed origins, and unsupported schemes are rejected.
- [x] Exact matching is deterministic.
- [x] Wildcard matching is one-label only and rejects apex, multi-level, suffix-confusion, IP, localhost, and public-suffix-like cases.
- [x] Environment policy rejects production HTTP and loopback.
- [x] Missing Origin is rejected for widget policy.
- [x] Partner API policy can bypass browser-origin validation.
- [x] Origin records are read by credential/environment and never by ID alone.
- [x] Public Access Gateway can invoke origin validation through explicit injection.
- [x] Safe events are emitted without raw headers.
- [x] No public endpoint or CORS middleware is added.
