# TASK-067B1 - Widget Revisioning, Draft/Publish Service Layer, RBAC, and Administration APIs

Status: Implemented
Phase: Sprint 3G - Widget Administration and Publishing
Type: Backend implementation

## Objective

Implement the backend foundation for authenticated widget administration: stable widget identity, draft configuration, immutable published revisions, active published revision resolution, tenant-scoped administration APIs, RBAC, optimistic concurrency, publication, rollback, and audit events.

## Source Documents Read

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/07_Public_Widget_Configuration_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/10_Widget_Controlled_Pilot_Deployment_and_Operations_Architecture.md`
- `implementation-pack/02_Architecture/11_Widget_Administration_Publishing_and_Embed_Management_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0012-public-widget-configuration-delivery.md`
- `docs/adr/0016-widget-deployment-versioning-and-release-model.md`
- `docs/adr/0017-widget-publishing-configuration-and-embed-management-model.md`
- Existing public credential, widget configuration, public widget, RBAC, audit, migration, and API test code.

## Implementation Summary

- Added a stable `Widget` model linked to the existing `PublicCredential` public widget key.
- Added `WidgetConfigurationRevision` snapshots with per-widget revision numbers, status, concurrency version, publication metadata, source revision provenance, and all currently supported public configuration fields.
- Added migration `0010_widget_revisioning` with forward-safe table creation and Python-side backfill from legacy `widget_configurations` rows.
- Added a framework-independent widget administration service for create, draft update, publish, revision history, revision detail, rollback, and diff summaries.
- Added authenticated workspace-scoped admin APIs under `/api/v1/workspaces/{workspace_id}/widgets` using the existing `org_owner` / `client_admin` RBAC boundary.
- Updated public configuration resolution to prefer the active published revision while retaining a legacy compatibility fallback.
- Added API tests for draft privacy, optimistic concurrency, publish validation, public ETag changes, rollback, tenant isolation, RBAC denial, and audit events.

## Data Model Strategy

`PublicCredential` remains the public key identity and lifecycle record. `Widget` is the stable administration object that owns operational status, pilot status, release channel, and the active published revision pointer. `WidgetConfigurationRevision` owns configuration snapshots only.

Operational controls, pilot allowlists, public-key rotation, allowed-origin CRUD, embed management, and preview grants remain outside B1.

## Draft and Publish Semantics

- Creating a widget creates an inactive public credential and an initial mutable draft revision.
- Draft updates are saved through optimistic concurrency using `concurrency_version`.
- Draft changes never affect the public configuration endpoint.
- Publishing validates the active key, active origins, operational status, and configuration payload.
- Publishing clones the draft into an immutable published revision, updates the widget active pointer atomically, supersedes the consumed draft, and creates a new editable draft from the published snapshot.
- Repeated stale publish attempts are rejected with `409` rather than silently creating duplicate published revisions.

## Rollback Semantics

Rollback selects a previous published revision, validates it against current publish rules, clones it into a new published revision, updates the active published pointer, creates a new draft, and records source revision provenance. Historical revisions are not mutated to become current.

## Public Configuration Integration

The public configuration endpoint now resolves:

1. Public credential.
2. Existing operational/pilot/origin policy.
3. Active published revision for the widget.
4. Legacy `WidgetConfiguration` only when no revisioned widget exists.

The existing public projection and ETag generation remain authoritative. Draft edits do not change the public ETag; publish and rollback do.

## Admin APIs

Implemented:

- `GET /api/v1/workspaces/{workspace_id}/widgets`
- `POST /api/v1/workspaces/{workspace_id}/widgets`
- `GET /api/v1/workspaces/{workspace_id}/widgets/{widget_id}`
- `GET /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/draft`
- `PATCH /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/draft`
- `POST /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/publish`
- `GET /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/revisions`
- `GET /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/revisions/{revision_id}`
- `POST /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/rollback`

## Deferred Work

- Full allowed-origin management API and UI: TASK-067B2.
- Public key rotation in the widget admin surface: TASK-067B2.
- Embed snippet/version management: TASK-067B2.
- Admin frontend, preview, publish workflow UI, revision history UI: later TASK-067B tasks.

## Verification

Focused verification performed:

```bash
npm run api:test -- tests/test_widget_admin_revisioning.py tests/test_public_widget_configuration_endpoint.py::test_public_widget_config_etag_conditional_get
```

Broader verification remains required before merge according to the task instructions.