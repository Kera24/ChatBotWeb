# Public Access Layer Foundation

Status: Implemented foundation only. No public route exists.

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

No public route is wired in this task. Future public endpoints must be introduced by a separate approved implementation task and must continue to route through this boundary rather than directly into RAG Orchestrator or dashboard authentication.
