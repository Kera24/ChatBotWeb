# TASK-064B3 - SDK Lifecycle, Iframe Mounting, and Public Browser API

Status: Implemented
Phase: Sprint 3D - Embeddable Widget

## Objective

Implement the browser-facing Widget SDK lifecycle, iframe mounting, one-instance runtime, and public JavaScript API.

## Scope

- Public SDK API: `init`, `open`, `close`, `toggle`, `destroy`, `isOpen`, `isReady`, `whenReady`, `on`, `off`, and `getState`.
- IIFE/global namespace: `window.YoranixWidget`.
- Script-tag auto-initialisation from approved `data-*` attributes.
- One-instance runtime and duplicate initialisation policy.
- DOM mounting of one container and one iframe.
- B2 handshake integration.
- Open/close command acknowledgement.
- Event system, focus restore, host visibility notification, bounded resize support, and development-only debug helper.

## Non-Goals

- No public config/session/message API clients.
- No session storage.
- No chat interface, final launcher styling, message composer, telemetry, React, backend changes, CDN publishing, npm publishing, streaming, or Markdown rendering.

## Acceptance Criteria

- SDK mounts the B2 iframe shell with safe attributes and URL contents.
- Runtime exposes only safe public methods and version metadata.
- Duplicate identical init reuses the existing runtime; conflicting init rejects safely.
- Open/close/toggle use protocol commands and validated acknowledgements.
- Destroy removes iframe/container/listeners/timers and allows clean reinitialisation.
- Root verification includes SDK and widget app tests/lint/build.
