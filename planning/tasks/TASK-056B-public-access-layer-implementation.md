# TASK-056B - Public Access Layer Implementation

## Task ID

TASK-056B

## Linked epic/story

- EPIC-004 - Public Access Layer
- TASK-056A - Public Access Layer Architecture
- TASK-055 - Public Widget Security Architecture

## Type

Implementation task. TASK-056A must be approved before this task starts.

## Objective

Create the reusable Public Access Layer code skeleton and provider-neutral contracts without adding public credentials, anonymous sessions, Redis rate limiting, public RAG endpoints, or widget functionality.

This task establishes implementation boundaries only.

## Required reading

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `planning/epics/EPIC-004-public-access-layer.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-050-rag-orchestrator-implementation.md`
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Implementation scope

Create the internal package:

```text
apps/api/app/access/
  __init__.py
  contracts.py
  errors.py
  gateway.py
  dependencies.py
  channels/__init__.py
  channels/base.py
  credentials/__init__.py
  credentials/contracts.py
  credentials/registry.py
  tenant_resolution/__init__.py
  tenant_resolution/service.py
  policies/__init__.py
  policies/models.py
  policies/registry.py
  observability/__init__.py
  observability/events.py
```

Do not create public API routes.

## Contract requirements

Define serialisable provider-neutral contracts:

- `PublicAccessRequest`
- `NormalisedAccessContext`
- `PublicAccessResponse`
- `PublicCredentialReference`
- `CostLimits`

Requirements:

- Request contracts must not accept trusted `organisation_id` or `workspace_id`.
- Tenant IDs appear only after server-side resolution.
- Raw channel-specific payloads stay outside the core contract where practical.
- Metadata is bounded and scalar-only.

## Safe public error model

Implement structured errors for:

- `invalid_credential`
- `disabled_credential`
- `expired_credential`
- `origin_not_allowed`
- `invalid_session`
- `expired_session`
- `request_too_large`
- `message_too_large`
- `rate_limited`
- `quota_exceeded`
- `unsupported_channel`
- `unsafe_request`
- `temporarily_unavailable`
- `safe_internal_error`

Each error exposes only stable public code, safe message, retryable flag, optional retry-after seconds, and HTTP status mapping.

## Channel foundation

Add an abstract channel adapter interface with:

- `channel_key`
- `display_name`
- `parse_request`
- `extract_public_credential`
- `extract_origin`
- `extract_session_token`
- `validate_request_shape`
- `normalise_message`
- `format_response`
- `format_error`
- `capabilities`
- `default_policy_profile`

Add only a deterministic internal test adapter. It must not be exposed publicly.

## Registries

Add isolated, explicit registries:

- `ChannelRegistry`
- `InMemoryCredentialRegistry`
- `AccessPolicyRegistry`

Registries must reject duplicate keys and support isolated construction in tests.

## Credential foundation

Define credential-neutral contracts for:

- `widget_public_key`
- `partner_api_key`
- `channel_installation`
- `future_webhook`

Supported statuses:

- `draft`
- `active`
- `disabled`
- `revoked`
- `expired`

No database model, migration, or credential-management API is allowed in this task.

## Policy foundation

Define policy profiles for:

- `internal_test`
- planned `widget`
- future `partner_api`

Policy fields include request/message/session/context/output/time limits, origin requirement, model allow-list, rate-limit failure posture, and retention placeholder.

## Tenant resolution

Resolve:

```text
public credential -> credential record -> organisation ID -> workspace ID -> policy profile
```

Use injected active/belongs checks. Reject inactive organisations, inactive workspaces, mismatches, invalid credentials, disabled credentials, revoked credentials, and expired credentials.

## Gateway skeleton

Initial flow:

1. Validate raw request shape.
2. Resolve channel adapter.
3. Parse and normalise request.
4. Resolve credential.
5. Resolve tenant context.
6. Resolve policy.
7. Validate request/message limits.
8. Produce a validated access result and safe response.

Stop before origin validation, rate limiting, anonymous sessions, abuse detection, cost enforcement, RAG orchestration, and response generation.

## Observability

Define safe event contracts for:

- `access.request.received`
- `access.channel.resolved`
- `access.credential.resolved`
- `access.credential.invalid`
- `access.tenant.resolved`
- `access.request.rejected`
- `access.request.validated`

Events must not include raw messages or secrets.

## Tests

Add unit tests for:

- request and response serialisation
- no trusted tenant IDs on request contracts
- safe error serialisation
- channel registry behaviour
- credential registry behaviour
- policy registry behaviour
- tenant resolution guarantees
- gateway success and rejection paths
- dashboard development headers rejected
- no public endpoint added
- isolated registries

## Documentation

Add `docs/04_Engineering/Public_Access_Layer_Foundation.md` and update the architecture document with concrete module paths.

## Constraints

Do not implement:

- public API routes
- widget config endpoint
- public message endpoint
- credential database tables
- credential admin API
- Redis
- rate limiting
- domain/origin validation
- anonymous sessions
- RAG calls
- widget SDK
- widget UI
- real API keys
- lead capture
- production analytics
- background jobs

## Verification

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- [x] Public Access Layer contracts exist internally.
- [x] Channel adapter interface exists.
- [x] Safe error codes are represented.
- [x] Tests prove dashboard/development auth headers are rejected by the public-access boundary.
- [x] Tests prove tenant context is server-resolved before future orchestration.
- [x] No public endpoint is exposed.
- [x] Documentation is updated.
