# TASK-065B1 - Widget Rendering Foundation, Design Tokens, and Structural Shell

Status: Implemented
Phase: Sprint 3E - Widget Experience

## Objective

Implement the Preact rendering foundation, validated design-token system, customer-brand mapping, and structural widget shell for the iframe visual application.

## Scope

Implemented:

- Preact rendering inside `apps/widget` only.
- UI controller that bridges existing framework-free widget state/services into Preact without exposing session tokens.
- Structural components for launcher, panel, header, status region, viewport, footer shell, loading state, and unavailable state.
- Typed design-token and contrast utilities.
- Client brand colour mapping with deterministic fallback.
- Light, dark, and auto/system token behavior.
- Iframe-contained CSS using projected custom properties.
- Safe raster asset boundary for future logo/avatar display.
- Preact render error boundary.
- Structural resize behavior through the existing widget state protocol.
- Unit and browser tests for shell, tokens, accessibility semantics, token isolation, theme variants, and bounds.

## Non-Goals

Not implemented:

- Full welcome state.
- Suggested questions.
- User/assistant message components.
- Composer/send UI.
- Citations.
- Privacy/terms content.
- Session-expiry workflow.
- Rate-limit recovery UI.
- Offline drafting.
- Final responsive/motion polish.
- Visual regression suite.
- Backend changes.
- SDK framework migration.
- Markdown rendering.
- Lead capture.
- Telemetry.

## Architecture Notes

Preact is isolated to `apps/widget`. `packages/widget-sdk` remains framework-free. Public API clients, session storage, message service, and the widget state store remain framework-independent.

The Preact shell receives only safe immutable state snapshots. The public session token is not passed to components, rendered into DOM, emitted through postMessage, or exposed in test hooks.

Backend output is still plain-text only. Message rendering and Markdown remain future tasks.

## Verification

Expected commands:

```bash
npm run widget:install
npm run widget:test
npm run widget:lint
npm run widget:build
npm run widget-sdk:test
npm run widget:e2e:chromium
npm run widget:e2e:extended
npm run verify
git diff --check
```

## Acceptance Criteria

- Preact is added only to `apps/widget`.
- The SDK remains framework-free.
- Structural shell renders safely after secure bootstrap/config loading.
- Tokens and brand mapping are deterministic and tested.
- Invalid or inaccessible branding cannot remove semantic/focus colours.
- Launcher/panel/header/viewport/footer shells exist without final chat features.
- Session tokens remain isolated.
- Existing B5 browser security tests continue to pass.
