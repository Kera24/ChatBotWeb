# Widget Administration Revisioning and Publishing

TASK-067B1 implements the backend foundation for widget administration without adding an admin frontend.

## Scope

The implementation adds stable widget identity, immutable configuration revisions, draft editing, publication, rollback, tenant-scoped admin APIs, optimistic concurrency, and audit events. It does not add allowed-origin management UI/API, public-key rotation, embed management, preview grants, or product analytics.

## Data Model

`Widget` is the stable administrative identity. It belongs to an organisation and workspace and references the existing `PublicCredential` record that supplies the public widget key. It stores operational status, pilot status, release channel, and the active published revision pointer.

`WidgetConfigurationRevision` stores configuration snapshots using the same fields currently supported by the public widget configuration contract: bot name, welcome message, launcher label, colours, asset paths, position, theme mode, suggestions, privacy/legal fields, language, citation capability, conversation-history capability, and initial suggestion count.

Published revisions are treated as immutable by the service layer. A consumed draft is superseded, and the service creates a fresh draft after publication or rollback.

## Migration

Migration `0010_widget_revisioning` creates `widgets` and `widget_configuration_revisions`. Existing rows in `widget_configurations` are backfilled into a stable widget and initial revision where data exists. The legacy table is retained for compatibility during rollout and downgrade.

Rollback of the migration drops the new revisioning tables only; it does not reconstruct revision history into the legacy mutable table.

## Draft Lifecycle

Creating a widget creates:

- a draft `PublicCredential` public widget key,
- a stable `Widget`,
- an initial draft revision.

Draft updates require `expected_concurrency_version`. A stale value returns `409` to avoid silent overwrite. Drafts are validated with the existing widget configuration validators but are not exposed through the public configuration endpoint.

## Publish Transaction

Publishing requires:

- authenticated tenant-scoped access,
- `org_owner` or `client_admin`,
- current draft revision identity,
- matching draft concurrency version,
- active public credential,
- at least one active allowed origin,
- enabled widget operational status,
- a valid public configuration payload.

The service clones the draft into a published revision, updates `Widget.active_published_revision_id`, supersedes the consumed draft, creates a new editable draft, records an audit event, and commits the transaction.

## Public Configuration and ETag

The public configuration resolver now prefers the widget active published revision. It falls back to the legacy `WidgetConfiguration` row only when no revisioned widget exists, preserving current runtime compatibility.

The public projection and ETag generator are unchanged. Draft edits do not change public ETags. Publishing or rollback changes the active revision content/identity and therefore changes the public ETag when the public payload changes.

## Rollback

Rollback targets a previous published revision. The target is cloned into a new published revision with `source_revision_id` provenance, the active pointer is updated, a new draft is created, and an audit event records the operation. Operational state, pilot state, release channel, public key, and origins are not modified by rollback.

## RBAC and Tenant Isolation

The B1 routes use the existing authenticated development-user dependency and require `org_owner` or `client_admin`. Every route scopes by organisation and workspace before loading widgets or revisions. Widget IDs and revision IDs are never trusted without tenant scope.

## Audit

B1 records:

- `widget.created`
- `widget_draft.updated`
- `widget.published`
- `widget_configuration.rolled_back`

Audit metadata uses widget/revision/public-credential identifiers and field summaries only. It does not include session tokens, conversation messages, answers, citations, or secrets.

## APIs

Implemented under `/api/v1/workspaces/{workspace_id}`:

- `GET /widgets`
- `POST /widgets`
- `GET /widgets/{widget_id}`
- `GET /widgets/{widget_id}/draft`
- `PATCH /widgets/{widget_id}/draft`
- `POST /widgets/{widget_id}/publish`
- `GET /widgets/{widget_id}/revisions`
- `GET /widgets/{widget_id}/revisions/{revision_id}`
- `POST /widgets/{widget_id}/rollback`

## Tests

`apps/api/tests/test_widget_admin_revisioning.py` covers draft concurrency, publish validation, draft privacy, public ETag behavior, rollback, audit events, RBAC denial, and cross-tenant denial.

## Deferred Work

TASK-067B2 should add allowed-origin management, public key lifecycle, embed versioning, and embed management APIs. Admin frontend and preview remain later tasks.