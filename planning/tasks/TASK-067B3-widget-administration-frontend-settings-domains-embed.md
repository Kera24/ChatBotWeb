# TASK-067B3 - Widget Administration Frontend: Settings, Domains, and Embed Management

Status: Implemented
Phase: Sprint 3G - Widget Administration and Publishing
Type: Frontend implementation

## Objective

Implement the first authenticated widget administration frontend for list, creation, draft settings, domain/origin management, public key display and rotation, embed setup, and managed/pinned SDK selection.

## Source Documents Read

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/11_Widget_Administration_Publishing_and_Embed_Management_Architecture.md`
- `implementation-pack/05_Design/02_Widget_UI_Interaction_Architecture.md`
- `docs/adr/0015-widget-ui-rendering-and-interaction-model.md`
- `docs/adr/0016-widget-deployment-versioning-and-release-model.md`
- `docs/adr/0017-widget-publishing-configuration-and-embed-management-model.md`
- TASK-067A, TASK-067B1, and TASK-067B2 task/engineering documents.
- Existing web app routes, dashboard shell, development tenant session, API client, tests, and CSS conventions.

## Implementation Summary

- Added authenticated widget administration routes:
  - `/widgets`
  - `/widgets/new`
  - `/widgets/[widgetId]`
- Added Widgets to the dashboard navigation.
- Added typed web API methods for widget list/create/detail/draft/origins/embed/key rotation/SDK versions.
- Added shared POST and DELETE support to the dashboard API client.
- Added widget list and empty state with status presentation and no full public key in list rows.
- Added creation form that creates an initial draft only; no auto-publish and no pilot enablement.
- Added widget detail shell with implemented tabs only: Overview, Appearance, Conversation, Domains, Embed.
- Added explicit Save draft behavior, dirty state, reset/discard, optimistic-concurrency conflict handling, and beforeunload protection while dirty.
- Added appearance settings for current draft contract fields.
- Added conversation settings for welcome, suggestions, privacy/legal, citations, and history capability fields.
- Added accessible suggested-question add/remove/reorder controls using buttons, not drag-only interaction.
- Added domains page for origin list/add/remove using B2 APIs and backend-authoritative validation/invariants.
- Added embed page for readiness, public key, inert snippet rendering, copy buttons, managed/pinned SDK selection, SRI display, and high-friction public-key rotation dialog.
- Added responsive styles under the existing global CSS conventions.
- Added component tests for list, creation, draft save, origin add, pinned SDK selection, inert snippets, and key rotation.

## Explicit Exclusions

B3 does not implement preview grants, draft iframe preview, publish UI, revision history UI, rollback UI, knowledge selection UI, pilot enablement mutation, global operational controls, analytics, deployment, or public widget runtime changes.

## Verification

Focused verification performed:

```bash
npm run web:test
npm run web:lint
npm run web:build
```

Broader repository verification is required before merge according to the task instructions.
