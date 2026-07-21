# Widget Admin Release Readiness Checklist

Status: Controlled-pilot administration gate

Run before enabling widget administration for controlled pilot use.

## Required Commands

- [ ] `python -m compileall apps/api/app`
- [ ] `npm run api:test`
- [ ] `npm run web:test`
- [ ] `npm run web:lint`
- [ ] `npm run web:build`
- [ ] `npm run widget:test`
- [ ] `npm run widget-sdk:test`
- [ ] `npm run widget:admin:e2e`
- [ ] `npm run widget:admin:a11y`
- [ ] `npm run widget:admin:security`
- [ ] `npm run widget:admin:release:verify`
- [ ] `npm run widget:pilot:verify`
- [ ] `npm run widget:pilot:readiness`
- [ ] `npm run widget:e2e:chromium`
- [ ] `npm run widget:e2e:a11y`
- [ ] `npm run widget:e2e:extended`
- [ ] `npm run verify`
- [ ] `git diff --check`

## Security Evidence

- [ ] Alpha tenant cannot view, edit, preview, publish, roll back, rotate, or inspect Beta widgets.
- [ ] Viewer role cannot mutate widgets, origins, keys, embed settings, knowledge scope, publish, or rollback.
- [ ] Stale draft publish attempts fail safely.
- [ ] Stale rollback attempts fail safely.
- [ ] Published revisions remain immutable.
- [ ] Knowledge options are tenant-scoped.
- [ ] Cross-tenant knowledge IDs are rejected.
- [ ] Deleted or unready selected knowledge blocks publish/rollback validation.
- [ ] Preview grant is short-lived, tenant-bound, widget-bound, actor-bound, and draft-bound.
- [ ] Preview token is not stored in audit, cookies, localStorage, parent DOM, or rendered URLs.
- [ ] Public session tokens do not grant preview access.
- [ ] Preview grants do not grant public anonymous session access.
- [ ] Old public key is rejected after rotation.
- [ ] Installation evidence resets for a rotated key until the new key is observed.
- [ ] Embed snippets are inert text and contain no `latest`, session token, API override, or arbitrary loader URL.
- [ ] Audit events cover create, draft update, origin add/remove, key rotation, embed version change, knowledge scope change, publish, and rollback.

## Accessibility Evidence

- [ ] Widget list, empty state, creation, settings, domains, embed, knowledge, preview, publish, history, and rollback are keyboard reachable.
- [ ] Dialogs have labels, descriptions, initial focus, and focus restoration expectations.
- [ ] Validation and conflict states are visible and not toast-only.
- [ ] Status is not colour-only.
- [ ] Preview iframe has a title and does not trap keyboard focus.
- [ ] Code snippets are selectable and horizontally scrollable without page overflow.
- [ ] Mobile layouts have no uncontrolled horizontal overflow.
- [ ] Manual NVDA/VoiceOver/zoom/high-contrast review is scheduled before GA.

## Classification

Passing this checklist means widget administration is ready for controlled pilot use. It does not mean GA readiness or production deployment has occurred.
