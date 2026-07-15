# Public Access Layer Foundation

Status: Implemented foundation with one public widget session endpoint.

## Module Layout

The reusable Public Access Layer skeleton lives under `apps/api/app/access`:

- `contracts.py` defines `PublicAccessRequest`, `NormalisedAccessContext`, `PublicAccessResponse`, and bounded metadata helpers.
- `errors.py` defines the safe public error catalog and HTTP status mapping.
- `gateway.py` defines `ChannelRegistry`, `ValidatedAccessResult`, and `PublicAccessGateway`.
- `dependencies.py` contains explicit factory helpers for isolated construction.
- `channels/base.py` defines the abstract channel adapter interface plus a deterministic internal test adapter.
- `credentials/contracts.py` and `credentials/registry.py` define credential records and an in-memory registry for tests.
- `tenant_resolution/service.py` resolves credential-owned tenant context through injected active/belongs checks.
- `policies/models.py` and `policies/registry.py` define policy profiles and registry behaviour.
- `observability/events.py` defines safe access event contracts and an in-memory sink.

## Implemented Flow

`PublicAccessGateway.validate_access` currently performs only boundary validation:

1. Receives a raw channel request.
2. Resolves a registered channel adapter.
3. Parses and normalises the request into `PublicAccessRequest`.
4. Rejects dashboard development headers in the test adapter.
5. Resolves the public credential from an injected registry.
6. Resolves tenant context server-side from the credential record.
7. Resolves the policy profile.
8. Checks request and message size limits.
9. Returns a `ValidatedAccessResult` with a `NormalisedAccessContext` and safe response.
10. Emits safe observability events.

The gateway intentionally stops before origin validation, rate limiting, anonymous session creation, abuse detection, cost enforcement, RAG orchestration, and response generation.

## Contract Example

```python
request = PublicAccessRequest(
    request_id="req-1",
    channel="internal_test",
    public_credential=PublicCredentialReference(
        credential_type="widget_public_key",
        public_identifier="public-test",
    ),
    message="How do I use this?",
)
```

`PublicAccessRequest` does not accept trusted `organisation_id` or `workspace_id`. Tenant IDs appear only in `NormalisedAccessContext` after credential resolution.

## Registry Usage

Registries are explicit objects, not hidden mutable singletons:

- `ChannelRegistry` registers adapters by channel key and rejects duplicates.
- `InMemoryCredentialRegistry` resolves public identifiers and rejects duplicate identifiers.
- `AccessPolicyRegistry` resolves bounded policy profiles and rejects duplicate keys.

Tests and future endpoints must construct isolated registries through `apps/api/app/access/dependencies.py` or direct dependency injection.

## Tenant Resolution Guarantees

The tenant resolver uses the credential record as the source of truth:

```text
public credential -> credential record -> organisation_id/workspace_id -> active checks -> policy profile
```

Incoming public requests cannot influence tenant selection with client-supplied tenant IDs. The resolver rejects inactive organisations, inactive workspaces, workspace/organisation mismatches, invalid credentials, disabled credentials, revoked credentials, and expired credentials.

## Safe Error Behaviour

Public errors expose only:

- stable code
- safe message
- retryable flag
- optional `retry_after_seconds`
- HTTP status mapping

They do not expose tenant IDs, provider internals, stack traces, database details, prompt content, or secret material.

## Observability

Access events contain safe metadata only: request ID, trace ID, channel, credential ID where safe, outcome, error code, and a latency placeholder. Raw message content and secrets are excluded.

Implemented event types include:

- `access.request.received`
- `access.channel.resolved`
- `access.credential.resolved`
- `access.credential.invalid`
- `access.tenant.resolved`
- `access.request.rejected`
- `access.request.validated`

## Explicitly Unimplemented

This foundation does not implement:

- public API routes
- widget config endpoint
- public message endpoint
- database credential tables
- credential admin API
- Redis rate limiting
- origin/domain validation
- anonymous sessions
- RAG calls
- widget SDK or UI
- real API keys
- lead capture
- production analytics
- background jobs

## Local Test Commands

```bash
cd apps/api
python -m pytest tests/test_public_access_layer.py
```

Repository-level verification remains:

```bash
npm run api:test
npm run verify
```

## Public Route Warning

TASK-061B wires public widget session creation. TASK-062B adds public widget configuration reads. Future public widget message endpoints must be introduced by separate approved tasks and must continue to route through this boundary rather than directly into RAG Orchestrator or dashboard authentication.

## TASK-057B Credential Persistence Update

TASK-057B adds the database-backed credential/configuration foundation while preserving the Public Access gateway boundary.

New persistent tables:

- `public_credentials`
- `credential_allowed_origins`
- `widget_configurations`

New implementation modules:

- `apps/api/app/access/credentials/repository.py`
- `apps/api/app/access/credentials/service.py`
- `apps/api/app/access/credentials/identifiers.py`
- `apps/api/app/access/credentials/origins.py`
- `apps/api/app/access/widget_config/repository.py`
- `apps/api/app/access/widget_config/service.py`
- `apps/api/app/access/widget_config/validation.py`

`DatabaseCredentialRegistry` can resolve persisted credentials into the existing `CredentialRecord` contract. `InMemoryCredentialRegistry` remains available for isolated tests.

The gateway behaviour is unchanged and no public route has been added. Runtime origin validation, Redis rate limiting, anonymous sessions, public session creation, and public config reads are implemented. Public message endpoint, public RAG, and widget UI remain unimplemented.

## TASK-058B Origin Validation Update

TASK-058B adds the runtime origin-validation foundation while preserving the no-public-route boundary.

New modules:

- `apps/api/app/access/origin_validation/contracts.py`
- `apps/api/app/access/origin_validation/normalisation.py`
- `apps/api/app/access/origin_validation/matcher.py`
- `apps/api/app/access/origin_validation/repository.py`
- `apps/api/app/access/origin_validation/service.py`
- `apps/api/app/access/origin_validation/errors.py`

`PublicAccessGateway` now accepts an optional injected `OriginValidationService`. When injected, origin validation runs after credential, tenant, policy, and request-limit checks. The gateway still stops before rate limiting, sessions, abuse checks, cost enforcement, RAG orchestration, and response generation.

No public endpoint, CORS middleware, Redis cache, anonymous session, widget SDK/UI, or RAG invocation was added.

## TASK-059B Distributed Rate Limiting Update

TASK-059B adds a distributed rate-limiting foundation while preserving the no-public-route boundary.

New modules:

- `apps/api/app/access/rate_limit/contracts.py`
- `apps/api/app/access/rate_limit/policies.py`
- `apps/api/app/access/rate_limit/identities.py`
- `apps/api/app/access/rate_limit/client_ip.py`
- `apps/api/app/access/rate_limit/token_bucket.py`
- `apps/api/app/access/rate_limit/redis_store.py`
- `apps/api/app/access/rate_limit/local_fallback.py`
- `apps/api/app/access/rate_limit/service.py`

`PublicAccessGateway` now accepts an optional injected `RateLimitService`. When injected, rate limiting runs after credential, tenant, policy, request-size, and origin checks. The gateway still stops before anonymous sessions, abuse detection, cost enforcement, RAG orchestration, and response generation.

No public endpoint, anonymous session, quota persistence, billing path, CORS middleware, widget SDK/UI, or RAG call was added.

## TASK-060B Anonymous Public Sessions Update

TASK-060B adds the persistent anonymous public-session foundation while preserving the no-public-route boundary.

New modules:

- `apps/api/app/access/sessions/contracts.py`
- `apps/api/app/access/sessions/tokens.py`
- `apps/api/app/access/sessions/repository.py`
- `apps/api/app/access/sessions/service.py`
- `apps/api/app/access/sessions/dependencies.py`

New database table:

- `public_sessions`

`PublicAccessGateway` now accepts an optional injected `PublicSessionService`. The session stage runs only for explicit `session_creation` or `session_validation` operations after credential/tenant/policy resolution, origin validation, and rate limiting. Session validation may optionally consume one message slot and still stops before RAG.

No public session endpoint, public message endpoint, public configuration endpoint, Redis session cache, CORS middleware, widget SDK/UI, conversation creation, or RAG invocation was added.

## TASK-061B Public Widget Session Endpoint Update

TASK-061B adds the first public widget endpoint:

```text
POST /api/v1/widget/{public_key}/sessions
OPTIONS /api/v1/widget/{public_key}/sessions
```

The session route lives in `apps/api/app/api/v1/public_widget.py` and uses the `WidgetChannelAdapter` plus `PublicAccessGateway` in `session_creation` mode. It creates anonymous public sessions only. It does not expose a public message endpoint, conversation creation, RAG invocation, AI Core invocation, widget SDK/UI, or global CORS middleware.

Session creation now runs through credential resolution, tenant resolution, widget configuration eligibility, Origin validation, `widget_session_create` rate limiting, and `PublicSessionService` session creation. Dynamic CORS is route-scoped and echoes only the validated Origin.
## TASK-062B Public Widget Configuration Endpoint Update

TASK-062B adds the second public widget endpoint:

```text
GET /api/v1/widget/{public_key}/config
OPTIONS /api/v1/widget/{public_key}/config
```

The route lives in `apps/api/app/api/v1/public_widget.py` and uses the `WidgetChannelAdapter` plus `PublicAccessGateway` in `config_read` mode. It returns only published, sanitised public widget configuration. It does not create sessions, conversations, messages, retrieval requests, RAG executions, AI Core executions, widget SDK/UI, or global CORS middleware.

Config reads run through credential resolution, tenant resolution, Origin validation, `widget_config_read` rate limiting, published-configuration eligibility, safe public projection, ETag generation, and dynamic route-scoped CORS. The only implemented public widget routes are now config read, session creation, and their route-scoped OPTIONS handlers.

The config response excludes tenant IDs, internal credential/config IDs, allowed origins, policy internals, provider/model/prompt details, retrieval/context/token limits, rate-limit rules, secret/hash fields, audit metadata, internal paths, and environment. Asset fields are projected only as safe HTTPS raster URLs or omitted.
