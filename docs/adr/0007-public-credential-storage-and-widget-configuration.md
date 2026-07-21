# ADR-0007: Public Credential Storage and Widget Configuration

Status: Proposed
Date: 2026-07-14

## Context

The Public Access Layer now has internal contracts and gateway foundations, but it intentionally does not persist public credentials or widget configuration. Future widget onboarding, key rotation, allowed-origin management, and external channel integrations need a persistent model that scales beyond a single website widget key.

The platform must support 10,000 organisations, multiple workspaces, multiple environments, and future credential types while preserving tenant isolation. No existing workspace should become public automatically.

## Decision

Use a generic `public_credentials` table with typed credentials, a separate normalised `credential_allowed_origins` table, and a separate `widget_configurations` table.

Chosen model:

```text
public_credentials
  -> credential_allowed_origins
  -> widget_configurations
```

Credential types include:

- `widget_public_key`
- `partner_api_key`
- `channel_installation`
- `webhook_secret`

Widget public keys are identifiers, not secrets. Partner API keys and webhook secrets are secret-bearing and store only strong verification hashes. Widget configuration is owned by credential for MVP so public config resolution is deterministic and environment-safe.

## Alternatives Considered

### Option A: One widget key directly on workspace

Pros:

- Very simple schema.
- Fast to implement for a single website widget.

Cons:

- Does not support rotation overlap cleanly.
- Does not support staging/production separation well.
- Does not support partner API keys or future channel installations.
- Encourages workspace-level public exposure by default.
- Hard to audit credential lifecycle independently.

Rejected because it optimises for the first widget only and weakens the platform-before-channel principle.

### Option B: Generic public_credentials table with typed credentials

Pros:

- Supports widget keys, partner API keys, channel installations, and webhook secrets.
- Centralises lifecycle, rotation, revocation, policy profile, capabilities, and audit events.
- Allows server-side public identifier resolution without trusting tenant IDs.
- Supports multiple environments and rotation overlap.
- Keeps no workspace public by default.

Cons:

- Requires type-specific validation in service layer.
- More schema and test surface than a workspace column.

Chosen because it provides the right reusable platform boundary without prematurely splitting every channel into separate tables.

### Option C: Separate tables per credential type

Pros:

- Strong type-specific columns.
- Less nullable data per table.

Cons:

- Duplicates lifecycle, status, environment, policy, and audit rules.
- Makes Public Access Layer resolution more complex.
- Adds cross-table uniqueness and rotation complexity.
- Slows future channel onboarding.

Rejected for MVP because common lifecycle and tenant-resolution rules are more important than per-type physical separation.

### Option D: External API gateway or key-management product

Pros:

- Mature key management and rate limiting features.
- Potential operational benefits at high scale.

Cons:

- Still needs tenant/workspace mapping and widget configuration in the product database.
- Adds vendor coupling before public channels exist.
- Does not solve widget branding, allowed-origin audit, or RAG policy resolution.
- Raises local development and test complexity.

Rejected for MVP. The internal model can later integrate with an external gateway if scale requires it.

## Rationale

The chosen model keeps credential identity, lifecycle, policy, and tenant mapping in one reusable place while allowing specialised tables for security-sensitive origin rules and widget-specific presentation settings.

A normalised `credential_allowed_origins` table is preferred over JSON because origins are security-sensitive, require validation, need uniqueness constraints, and must be auditable. Arbitrary origin strings in JSON would make future origin validation easier to misconfigure.

A per-credential widget configuration is preferred for MVP because it prevents staging/production confusion and makes rotation deterministic. Workspace/environment-level shared templates can be added later when multiple credentials need shared branding.

## Consequences

Positive:

- Public credential resolution is generic and reusable by future channels.
- Widget keys can be rotated without making a workspace public by default.
- Secret-bearing credentials can use one-time display and hash-only storage.
- Allowed origins are queryable, auditable, and normalised.
- Widget configuration can be cached and versioned safely.
- Dashboard admin APIs can enforce tenant-safe resource access.

Trade-offs:

- More tables than the old `widget_settings` placeholder.
- More service validation is required for type-specific rules.
- Public config resolution needs joins or cache composition.
- Rotation and active-key constraints require careful service logic and tests.

## Security Rules

- Widget public keys are not secrets and do not grant dashboard access.
- Secret-bearing credential values are returned once and stored only as hashes.
- No credential should be created automatically.
- No workspace becomes public by default.
- Admin credential paths must include organisation and workspace scope.
- Public resolution never trusts client-supplied organisation or workspace IDs.
- Revoked credentials cannot be reactivated.
- Disabled organisation or workspace makes all related credentials unusable.
- Public config responses must exclude tenant IDs, credential database IDs, policy internals, provider details, allowed-origin lists, audit metadata, internal asset paths, and secret hashes.

## Non-Goals

This ADR does not implement:

- SQLAlchemy models.
- Alembic migrations.
- Repositories or services.
- Admin endpoints.
- Public endpoints.
- Dashboard UI.
- Origin validation runtime.
- Redis caching or rate limiting.
- Anonymous sessions.
- Public RAG.
- Widget code.

## Related Documents

- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
