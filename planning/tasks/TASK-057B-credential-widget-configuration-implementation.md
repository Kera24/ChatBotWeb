# TASK-057B - Credential and Widget Configuration Implementation

## Task ID

TASK-057B

## Linked architecture

- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`

## Type

Implementation task.

## Status

Implemented.

## Objective

Implement the persistent database, repository, service, validation, and authenticated admin API foundation for public credentials, allowed origins, and widget configurations.

No public widget configuration endpoint, public message endpoint, anonymous session, Redis limiter, RAG invocation, widget SDK, or widget UI is implemented by this task.

## Implemented scope

- SQLAlchemy models for `public_credentials`, `credential_allowed_origins`, and `widget_configurations`.
- Alembic migration `0007_public_credentials_widget_config`.
- High-entropy widget public identifier generation.
- Tenant-safe credential repositories and services.
- Credential lifecycle transitions and rotation foundation.
- Allowed-origin normalisation and persistence.
- Widget configuration validation, draft upsert, publish, and safe public configuration projection.
- Database-backed Public Access credential resolver alongside the existing in-memory registry.
- Authenticated development-dashboard admin APIs for credential/config management.
- Audit events for credential, origin, and widget configuration changes.
- Automated tests for migration, services, repositories, APIs, RBAC, and safe responses.

## Explicitly not implemented

- Public widget config endpoint.
- Public message endpoint.
- Runtime Origin-header validation.
- Redis rate limiting.
- Anonymous sessions.
- Partner secret one-time creation flow.
- Widget SDK/UI.
- Asset upload.
- RAG invocation.
- Public credential cache.
- Production authentication changes.

## Verification

Required commands:

```bash
docker compose up -d postgres redis
cd apps/api
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
cd ../..
npm run api:test
npm run verify
```

## Acceptance criteria

- [x] Models and migration exist.
- [x] No credential rows are created automatically.
- [x] No workspace becomes public by migration.
- [x] Tenant-safe repositories/services exist.
- [x] Public identifiers contain no tenant information.
- [x] Lifecycle and rotation rules are implemented.
- [x] Allowed origins are normalised and validated.
- [x] Widget configuration validation and publishing are implemented.
- [x] Admin APIs are protected by org_owner/client_admin RBAC.
- [x] Safe responses exclude secret hashes and hidden metadata.
- [x] Public Access Layer can use a database-backed credential resolver.
- [x] Tests cover models, migration, services, APIs, RBAC, and audit events.
