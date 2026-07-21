# Widget Preview, Publishing, History, Knowledge, and Installation Verification

TASK-067B4 completes the authenticated administration workflow around the revision model introduced in TASK-067B1 and the origin/key/embed APIs introduced in TASK-067B2.

## Knowledge Scope

Widget draft revisions now carry `knowledge_scope_json`, a list of tenant-owned document IDs. The admin API lists only documents from the authenticated organisation/workspace and rejects submitted resource IDs that do not belong to the widget tenant. Published revisions freeze the selected scope, and rollback restores the previous scope by creating a new immutable publication revision.

Readiness is derived from document and active-version state:

- `ready`: document status is ready and active version processing is completed.
- `indexing`: document/version is still processing.
- `failed`: document/version processing failed.
- `unavailable`: no active usable version exists.

Publish validation blocks selected resources that are not ready. Empty scope is allowed as a fallback-capable configuration but returned as a warning.

## Preview Grants

Preview grants are authenticated admin-only tokens created by `POST /widgets/{widget_id}/preview-grant`. The grant is HMAC signed, short lived, and bound to actor, organisation, workspace, widget, and draft revision. The token is returned only to the admin frontend and is not logged or embedded in public configuration.

The B4 frontend implements a config-faithful iframe preview using the saved draft configuration and the preview grant lifecycle. It preserves draft/public separation and does not expose draft data through the anonymous public configuration endpoint. Full preview message/RAG execution remains a B5 hardening target.

## Publish Workflow

The Publish page calls side-effect-free validation before enabling confirmation. Validation returns:

- publishable boolean
- blocking errors
- warnings
- draft-versus-published diff summary
- selected knowledge readiness

Publishing still uses the B1 transaction: validate, create immutable published revision, atomically set the active published pointer, retain history, create/continue draft, and audit the action. Pilot and operational state are not changed by publication.

## Revision History and Rollback

The History page lists revisions, loads immutable revision detail, and calls the rollback API for historical published revisions. Rollback creates a new published revision cloned from the selected historical revision and records `source_revision_id`; it does not mutate previous revisions.

## Installation Verification

B4 avoids server-side crawling to prevent SSRF risk. Instead, valid public configuration requests from allowed origins record passive installation evidence:

- widget ID
- public credential ID
- approved origin
- optional SDK version header
- optional protocol major header
- last seen timestamp

The Embed page displays observed/not observed status per allowed origin. This is operational installation evidence, not product analytics, and stores no session token, message content, user identity, or answer text.

## Tests

Focused tests cover tenant-scoped knowledge options, cross-tenant scope rejection, preview grant creation, publish validation, installation observation, and cross-tenant installation-status denial. Existing widget admin frontend tests now render the B4 data contract and keep embed snippets inert.

## Deferred To TASK-067B5

- Full authenticated browser E2E for create-configure-preview-publish-rollback.
- Axe/manual accessibility validation for the new admin tabs.
- Preview message/RAG execution if required after security review.
- Expanded audit review and pilot admin release gate.

## TASK-067B5 Admin Release Gate Update

TASK-067B5 adds an administration hardening gate for controlled pilot use. The gate combines API hardening tests, admin frontend workflow tests, public widget pilot verification, pilot readiness, and a machine-readable report at `artifacts/widget-admin-readiness/report.json`.

New commands:

```bash
npm run widget:admin:e2e
npm run widget:admin:a11y
npm run widget:admin:security
npm run widget:admin:release:verify
```

The current preview remains configuration-faithful. Full conversational/RAG draft preview is deferred until a separate preview session/message boundary is designed and implemented.
