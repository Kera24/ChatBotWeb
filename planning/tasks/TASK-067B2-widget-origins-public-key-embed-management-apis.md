# TASK-067B2 - Widget Allowed Origins, Public Key Lifecycle, Embed Versioning, and Embed Management APIs

Status: Implemented
Phase: Sprint 3G - Widget Administration and Publishing
Type: Backend implementation

## Objective

Implement authenticated backend administration support for widget allowed origins, public-key rotation, embed SDK version selection, safe embed snippet generation, embed status metadata, RBAC, tenant isolation, and audit events.

## Source Documents Read

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/09_Embeddable_Widget_SDK_Architecture.md`
- `implementation-pack/02_Architecture/10_Widget_Controlled_Pilot_Deployment_and_Operations_Architecture.md`
- `implementation-pack/02_Architecture/11_Widget_Administration_Publishing_and_Embed_Management_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0014-widget-sdk-and-iframe-delivery.md`
- `docs/adr/0016-widget-deployment-versioning-and-release-model.md`
- `docs/adr/0017-widget-publishing-configuration-and-embed-management-model.md`
- TASK-066B1, TASK-066B3, TASK-067A, and TASK-067B1 planning/engineering documents.
- Existing public credential, origin validation, widget admin, release artifact, audit, RBAC, and public widget config/session/message code.

## Implementation Summary

- Reused the existing `CredentialAllowedOrigin` model as the stable widget/public-credential origin boundary.
- Added authenticated origin list/add/remove APIs under the existing workspace widget admin route family.
- Normalized default origin ports so `https://example.com:443/` and `https://example.com` conflict as the same canonical origin.
- Enforced exact-origin administration, wildcard rejection, server-side origin limits, and a final-active-origin removal invariant for published enabled widgets.
- Added immediate public-key rotation that revokes the old credential, creates a replacement key, preserves active origins, keeps configuration revisions unchanged, and audits safe key fingerprints only.
- Added widget embed preferences on the stable `Widget` identity: `managed_major` by default with optional `pinned` SDK semver.
- Added a provider-neutral SDK version registry at `deployment/widget/sdk-versions.json` and embed metadata/snippet generation from approved SDK metadata only.
- Added public config ETags keyed by public identifier to prevent cross-key conditional cache confusion after rotation.
- Added API tests for origin normalization/security, final-origin protection, key rotation cutover, cache isolation, embed version selection, tenant isolation, RBAC denial, and audit events.

## Admin APIs

Implemented:

- `GET /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/origins`
- `POST /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/origins`
- `DELETE /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/origins/{origin_id}`
- `POST /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/rotate-key`
- `GET /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/embed`
- `PATCH /api/v1/workspaces/{workspace_id}/widgets/{widget_id}/embed`
- `GET /api/v1/workspaces/{workspace_id}/widget-sdk-versions`

All endpoints use the existing authenticated workspace/organisation route convention and the `org_owner` / `client_admin` RBAC boundary. Tenant context comes from authenticated request context and route/query scoping, not request body tenant IDs.

## Origin Policy

Origins remain credential-bound and are not configuration revisions. Adding or removing an origin can affect runtime origin authorization immediately without mutating historical published configuration.

Policy implemented:

- Exact origins only.
- Wildcards rejected by the widget admin service.
- Existing production HTTPS/localhost rules remain enforced by the shared origin validator.
- Scheme and host are lowercased.
- Default ports are removed.
- Duplicate canonical origins are rejected by existing uniqueness behavior.
- Maximum active origins per widget: 20.
- A published enabled widget cannot remove its final active origin.

## Public Key Rotation

Rotation is immediate cutover:

1. Tenant-scoped widget is loaded.
2. Expected current credential ID must match.
3. Old credential is marked revoked with rotation timestamps.
4. A new unique public identifier is generated through the existing credential generator.
5. Active origins are copied to the replacement credential.
6. The stable widget points to the replacement credential.
7. Audit records safe old/new key fingerprints, not full keys.

Old embed snippets stop resolving because the old public key is revoked. The new key resolves the same active published revision. Historical revisions are not changed.

Existing sessions remain bound to the credential/session policy already implemented in the public session service. Since the old credential is revoked and public routes validate active credentials on use, old-key flows are rejected rather than silently rebound.

## Embed Model

`Widget.embed_version_mode` supports:

- `managed_major`: default, uses `/widget-sdk/v1/loader.js`.
- `pinned`: uses an approved immutable semantic loader path, currently `/widget-sdk/v0.1.0-foundation.0/loader.js`.

The API never accepts arbitrary SDK URLs, `latest`, API origin overrides, iframe origin overrides, session tokens, or secrets. Release channel remains a separate widget operational field and is reported as metadata only.

Pinned snippets include SRI only when an approved release artifact manifest provides it. Managed major-alias snippets do not include fixed SRI because the alias is intentionally mutable by operations.

## Embed Readiness Codes

Admin-only embed metadata reports machine-readable readiness codes:

- `ready`
- `unpublished`
- `no_allowed_origins`
- `operationally_disabled`
- `pilot_not_enabled`
- `unsupported_sdk_version`

`published`, `pilot_status`, `operational_status`, and `release_channel` remain separate fields.

## Deferred Work

- Admin frontend pages for domains, embed setup, settings, and publish workflow.
- Preview grants and visual preview.
- Public key dual-key grace period.
- Installation crawler/verification.
- Knowledge-selection UI.
- Production deployment or monitoring vendor integration.

## Verification

Focused verification performed:

```bash
npm run api:test -- tests/test_widget_admin_origins_embed.py tests/test_widget_admin_revisioning.py tests/test_public_widget_configuration_endpoint.py
```

Broader verification remains required before merge according to the task instructions.
