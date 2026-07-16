# Current Sprint

Current phase: Sprint 3D - Embeddable Widget
Current task: TASK-064B3 - SDK Lifecycle, Iframe Mounting, and Public Browser API

## Active Objective

Implement the browser-facing Widget SDK lifecycle, iframe mounting, one-instance runtime, and public JavaScript API over the existing secure iframe shell.

## Guardrails

- Do not call public config/session/message APIs.
- Do not store session tokens or use browser storage.
- Do not implement the visual launcher, chat panel, message list, composer, or final widget UI.
- Do not add telemetry, backend changes, CDN deployment, npm publishing, React, streaming, or Markdown rendering.
- Keep public API callbacks and errors safe: no stack traces, tenant IDs, session tokens, messages, or raw internal controller objects.

## Definition Of Done

- `window.YoranixWidget` and ESM exports expose the approved public API.
- Script-tag auto-init reads only approved `data-*` attributes.
- One-instance runtime mounts one container and one iframe.
- Runtime completes B2 handshake with exact origin/source validation.
- Open/close/toggle use validated `widget_state_changed` acknowledgements.
- Focus, resize, visibility, debug, event, and destroy foundations are covered by tests.
- Documentation and smoke harness are updated.
