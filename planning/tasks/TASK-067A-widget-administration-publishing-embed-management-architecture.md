# TASK-067A - Widget Administration, Publishing, and Embed Management Architecture

Status: Proposed architecture task
Phase: Sprint 3G - Widget Administration and Publishing
Type: Architecture and planning only

## Objective

Define the authenticated administration, publishing, configuration lifecycle, allowed-origin management, embed-code management, preview, versioning, audit, and operational-control architecture for embeddable Yoranix widgets.

This task does not implement admin UI, publishing APIs, migrations, production runtime behavior, deployment infrastructure, or production deployment.

## Source Documents Read

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/07_Public_Widget_Configuration_Endpoint_Architecture.md`
- `implementation-pack/02_Architecture/10_Widget_Controlled_Pilot_Deployment_and_Operations_Architecture.md`
- `implementation-pack/05_Design/02_Widget_UI_Interaction_Architecture.md`
- `docs/04_Engineering/Public_Widget_Configuration_Endpoint.md`
- `docs/adr/0016-widget-deployment-versioning-and-release-model.md`
- Current API models and services for public credentials, allowed origins, widget configuration, RBAC, audit events, and operational controls.

## Current Implementation Findings

- Authenticated public-credential management currently exists under workspace-scoped API routes using development-header auth and `org_owner` / `client_admin` role checks.
- `PublicCredential` is the current stable public widget key record and supports status, environment, capabilities, rotation group, parent credential, and audit events.
- `CredentialAllowedOrigin` stores normalized scheme, hostname, port, wildcard flag, environment, and active state.
- `WidgetConfiguration` is currently one mutable row per credential with `status`, `configuration_version`, and `published_at`.
- Updating a published widget configuration currently mutates the row and flips status back to `draft`; this is not sufficient for the target draft-plus-published revision model.
- Operational controls from TASK-066B3 are server-side configuration controls, not tenant-admin UI controls.

## Architecture Decision Summary

TASK-067A selects stable widget identity plus immutable versioned configuration revisions with one active published revision.

Publication, pilot enablement, operational enabled/disabled state, public key state, and deployment release channel are separate concepts.

## Out Of Scope

- Admin UI implementation.
- Admin publishing API implementation.
- Database migrations.
- Runtime public widget behavior changes.
- Deployment/CDN/DNS changes.
- Monitoring vendor integration.
- Lead capture, analytics dashboards, streaming, Markdown, file upload, human handoff, billing, or GA declaration.

## Deliverables

- `implementation-pack/02_Architecture/11_Widget_Administration_Publishing_and_Embed_Management_Architecture.md`
- `docs/adr/0017-widget-publishing-configuration-and-embed-management-model.md`
- Sprint and project context updates.

## Acceptance Criteria

- Widget lifecycle, draft/published architecture, revision model, publish semantics, public config propagation, rollback, public key lifecycle, allowed origins, preview, knowledge scope, embed management, SDK version/channel policy, pilot/operational status separation, RBAC, audit, admin IA, security threats, implementation split, and diagrams are documented.
- ADR-0017 records the configuration/publishing decision.
- No runtime/admin implementation is added.

## Verification

Run:

```bash
git diff --check
```

## Next Recommended Task

`TASK-067B1 - Widget Data Model, Revisioning, Admin Service Layer, RBAC, Draft, and Publish APIs`
