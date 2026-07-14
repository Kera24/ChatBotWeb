# TASK-057A - Credential and Widget Configuration Architecture

## Task ID

TASK-057A

## Linked epic/story

- EPIC-004 - Public Access Layer
- ADR-0005 - Public Widget Security Boundary
- ADR-0006 - Public Access Layer Bounded Context
- ADR-0007 - Public Credential Storage and Widget Configuration

## Type

Architecture task. Must be approved before TASK-057B implementation starts.

## Status

Proposed architecture complete.

## Objective

Design the persistent credential and widget-configuration subsystem that will support secure widget onboarding, key rotation, branding, allowed-origin configuration, and future public channels.

The design supports 10,000 organisations and future credential types without exposing public chat, public config endpoints, or widget UI.

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
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/02_Architecture/02_Database_Design.md`
- `docs/06_Security/01_Security_and_RBAC_Model.md`
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Deliverables

- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `.ai/CURRENT_SPRINT.md` updated to Sprint 3B / TASK-057A
- `.ai/PROJECT_CONTEXT.md` updated with credential/public exposure guardrails if needed

## Bounded context

The credential and widget configuration subsystem is part of the Public Access Layer.

It owns:

- Public credential persistence.
- Public identifier generation.
- Secret hashing for secret-bearing credentials.
- Widget configuration persistence.
- Credential lifecycle.
- Credential rotation and revocation.
- Environment separation.
- Allowed-origin configuration storage.
- Channel capabilities.
- Policy-profile assignment.
- Dashboard credential management rules.
- Audit events.
- Cache invalidation design.

It does not own:

- Origin validation execution.
- Redis rate limiting.
- Anonymous sessions.
- RAG execution.
- Public message processing.
- Widget rendering.
- Billing.

## Architecture decisions

- Use a generic `public_credentials` table with typed credentials.
- Use a normalised `credential_allowed_origins` table rather than storing arbitrary origin strings in JSON.
- Use a `widget_configurations` table owned by credential for MVP.
- Allow multiple active widget keys only for explicit rotation overlap or future explicitly approved parallel deployment policy.
- Treat widget public keys as public identifiers, not secrets.
- Treat partner API keys and webhook secrets as secret-bearing credentials shown once and stored only as hashes.
- Do not create any credential automatically.
- Do not make any workspace public by default.

## Proposed future schema

Future implementation should add:

- `public_credentials`
- `credential_allowed_origins`
- `widget_configurations`

The detailed fields, constraints, indexes, lifecycle rules, rotation model, validation rules, cache rules, audit events, and threat model are specified in `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`.

## Proposed future admin APIs

Proposed authenticated dashboard APIs only:

- `GET /api/v1/workspaces/{workspace_id}/public-credentials?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials?organisation_id=...`
- `GET /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}?organisation_id=...`
- `PATCH /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/activate?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/disable?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/revoke?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/rotate?organisation_id=...`
- `GET /api/v1/workspaces/{workspace_id}/widget-config?organisation_id=...`
- `PUT /api/v1/workspaces/{workspace_id}/widget-config?organisation_id=...`
- `POST /api/v1/workspaces/{workspace_id}/widget-config/publish?organisation_id=...`

Do not implement these in TASK-057A.

## RBAC decision

- `org_owner`: credential/config read and write.
- `client_admin`: credential/config read and write within managed workspace.
- `viewer`: no credential detail access and no writes. A future dashboard may show high-level deployment status only.
- `contributor`: excluded.
- `super_admin`: future platform-admin override only, audited separately.

Rationale: public credentials, origins, and rotation are security-sensitive deployment controls.

## Implementation sequence

Future tasks should be split as follows:

1. `TASK-057B` credential/widget schema implementation.
2. Repository and service implementation.
3. Credential admin APIs.
4. Widget configuration APIs.
5. Rotation service hardening.
6. Dashboard credential UI.
7. Origin validation architecture and implementation.
8. Public config endpoint.
9. Security testing and abuse monitoring.

## Future test strategy

Future implementation must test:

- Identifier uniqueness.
- Widget public key non-secret behaviour.
- Partner secret one-time return and hash verification.
- Tenant-safe admin reads.
- Cross-tenant denial.
- Lifecycle transitions.
- Revoked credential resolution failure.
- Expired credential resolution failure.
- Multiple keys during rotation.
- Origin normalisation.
- Wildcard restrictions.
- Widget configuration validation.
- XSS rejection.
- Public config privacy exclusions.
- Cache invalidation.
- Disabled organisation/workspace behaviour.
- No automatic public exposure.

## Explicit non-implementation constraint

Do not implement in this task:

- SQLAlchemy models.
- Alembic migrations.
- Repositories.
- Services.
- Admin endpoints.
- Public endpoints.
- Dashboard UI.
- Origin validation runtime.
- Redis.
- Anonymous sessions.
- RAG.
- Widget code.

## Verification

Run:

```bash
git diff --check
```

No automated runtime tests are required because this is planning-only.

## Acceptance criteria

- [x] Persistent credential and widget models are fully defined.
- [x] Credential type and lifecycle rules are explicit.
- [x] Allowed-origin model is selected.
- [x] Rotation is defined.
- [x] Safe public config contract is defined.
- [x] RBAC and admin APIs are specified.
- [x] Threat model and diagrams are complete.
- [x] ADR records the chosen storage model.
- [x] Implementation is sequenced.
- [x] No code or migration is added.
