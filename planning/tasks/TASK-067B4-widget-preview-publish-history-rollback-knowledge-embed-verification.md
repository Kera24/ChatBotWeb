# TASK-067B4 - Widget Preview, Publish Workflow, Revision History, Rollback, Knowledge Scope, and Embed Verification

Status: Implemented
Sprint: Sprint 3G - Widget Administration and Publishing

## Objective

Complete the authenticated widget administration workflow for saved drafts, knowledge scope, preview, publication, revision history, rollback, and embed installation evidence without changing production deployment or broad widget runtime behavior.

## Scope Implemented

- Tenant-scoped knowledge option listing and draft knowledge-scope update.
- Knowledge scope persisted on configuration revisions through `knowledge_scope_json`.
- Publish validation endpoint that reports configuration, origin, and knowledge-readiness blockers without mutating state.
- Short-lived authenticated preview grants bound to tenant, widget, actor, and draft revision.
- Admin frontend tabs for Knowledge, Preview, Publish, History, and installation evidence on Embed.
- Revision history/detail and rollback UI wired to immutable revision APIs.
- Passive installation evidence recorded from valid public configuration requests for approved origins.
- Installation status API for authenticated widget administrators.
- Public retrieval scope filtering by active published revision knowledge scope.
- Focused API and frontend regression tests.

## Boundaries Preserved

- No production deployment or DNS changes.
- No public draft configuration endpoint.
- No arbitrary external crawling for installation verification.
- No analytics dashboard or product telemetry.
- Pilot, operational status, publication, and release channel remain separate.
- Preview grants are not public sessions and do not publish draft state.

## Verification Notes

- `npm run web:lint`
- `npm run web:build`
- `npm run web:test`
- `python -m compileall apps/api/app`
- `npm run api:test -- tests/test_widget_admin_revisioning.py tests/test_widget_admin_origins_embed.py`

## Residual Work

TASK-067B5 should add deeper authenticated browser E2E, accessibility audits for the full admin flow, security hardening, audit review, and pilot admin release gates.
