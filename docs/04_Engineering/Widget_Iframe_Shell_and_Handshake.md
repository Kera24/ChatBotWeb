# Widget Iframe Shell and Handshake

TASK-064B2 adds the non-visual iframe application shell and strict postMessage handshake foundation for the future embeddable widget.

## App Structure

```text
apps/widget/
  package.json
  tsconfig.json
  vite.config.ts
  index.html
  scripts/check-size.mjs
  src/
    bootstrap.ts
    constants.ts
    errors.ts
    handshake.ts
    lifecycle.ts
    main.ts
    parent-origin.ts
    protocol.ts
    style.css
  test/
```

The app uses Vite and TypeScript with no React. It builds a static deployable iframe shell.

## Shared Protocol

Shared protocol definitions live in `packages/widget-sdk/src/protocol` and are exported by the SDK package. Both the SDK-side controller and iframe app consume the same protocol constants, envelope types, safe errors, and validators.

The envelope contains:

- `protocol`
- `version`
- `messageId`
- `type`
- `source`
- `payload`
- `sentAt`

Current message types are limited to handshake and lifecycle placeholders:

- iframe to loader: `iframe_ready`, `widget_ready`, `handshake_error`, `resize_request`, `widget_state_changed`
- loader to iframe: `initialise`, `open`, `close`, `destroy`, `host_visibility_changed`

No chat messages, config payloads, API responses, session tokens, tenant IDs, or telemetry cross this boundary.

## Bootstrap Strategy

The SDK iframe URL builder creates URLs like:

```text
https://widget.yoranix.com/embed/{public_key}?parent_origin=https%3A%2F%2Fexample.com&protocol=1&sdk=v1
```

Only the public widget key and bounded version/origin hints appear in the URL. Session tokens, tenant IDs, conversation IDs, and arbitrary query strings are excluded.

The iframe validates:

1. `parent_origin` is a normalised origin.
2. HTTPS is required outside localhost development.
3. `document.referrer` origin matches when available.
4. The first `initialise` message arrives from the same origin and actual parent window.
5. Protocol, version, source, type, and payload are valid.

The iframe sends `iframe_ready` to the exact validated parent origin. Wildcard `targetOrigin` is rejected by the send helper.

## State Machines

SDK-side handshake states:

- `idle`
- `waiting_for_iframe_ready`
- `initialising`
- `ready`
- `failed`
- `destroyed`

Iframe states:

- `booting`
- `waiting_for_initialise`
- `ready_closed`
- `ready_open`
- `failed`
- `destroyed`

Invalid transitions throw internally and surface safe failure behavior in the shell.

## Timeouts And Replay

The SDK controller has:

- iframe-ready timeout
- initialise-ack timeout
- one bounded ready retry
- destroy cleanup for listeners and timers
- bounded recent `messageId` replay tracking

The iframe rejects duplicate `initialise` messages and ignores repeated message IDs where appropriate.

## Iframe Shell

The current iframe page renders only neutral status text:

- loading
- ready
- unavailable

It uses semantic `role="status"`, `aria-live="polite"`, minimal CSS, no external fonts, no animation dependency, no API calls, and no storage writes.

## Sandbox Contract

Recommended iframe attributes are exported from the SDK:

```text
sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
allow=""
referrerpolicy="strict-origin-when-cross-origin"
title="Yoranix chat widget"
loading="lazy"
```

`allow-scripts` plus `allow-same-origin` is accepted only because the widget must later own origin storage and API calls on a dedicated widget origin. Compensating controls are strict postMessage, dedicated origin, CSP, no same-site sensitive cookies, and no token transfer to the parent page.

## Header Guidance

Future deployment should set iframe-app headers deliberately:

- CSP limiting scripts/styles/connect/images to approved widget/API origins.
- No `X-Frame-Options`, because this app must be embedded.
- `frame-ancestors` must be designed carefully; dynamic customer origin allowlisting is not usually practical in a static CDN shell.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- Minimal `Permissions-Policy`; no camera, microphone, clipboard, geolocation, or downloads.
- Cache hashed assets aggressively and keep the HTML shell on a shorter TTL.

## Build And Test Commands

From the repository root:

```bash
npm run widget:install
npm run widget:test
npm run widget:lint
npm run widget:build
npm run verify
```

`npm run widget:build` enforces initial shell budgets:

- JavaScript <= 30 KiB gzip
- CSS <= 10 KiB gzip

## Current Exclusions

This task does not implement public config/session/message API calls, session storage, visual widget UI, launcher, chat panel, final global SDK lifecycle API, telemetry, backend changes, CDN deployment, or SRI generation.

## Lifecycle Runtime

The SDK package now includes runtime modules under `packages/widget-sdk/src/runtime` for one-instance lifecycle, DOM mounting, public API exposure, events, readiness, visibility, focus, resize, and debug foundations.

The IIFE bundle installs `window.YoranixWidget` only when it can do so without overwriting an unrelated global. Auto-init reads approved `data-*` attributes from the current script.

No public backend API clients, session storage, visual widget UI, or telemetry are included.

## B3 Runtime Integration

TASK-064B3 integrates the shell with the SDK runtime. The iframe shell now acknowledges `open`, `close`, `destroy`, and `host_visibility_changed` lifecycle messages, emits bounded placeholder `resize_request` messages, and updates only neutral accessible status text.

The shell still does not call public APIs, use storage, render chat content, or implement final widget UI.

## API Bootstrap Update

TASK-064B4 moves `widget_ready` behind public configuration loading. The iframe still sends `iframe_ready` immediately after bootstrap, but it sends `widget_ready` only after config has been fetched or revalidated from a safe cache.

No session token, public config payload, message, answer, citation, or API error body is sent to the loader through postMessage.

## Browser Handshake Verification

TASK-064B5 verifies the handshake in Chromium with real browser postMessage, exact target origins, forged-message rejection, malformed iframe message handling, and no wildcard `targetOrigin` usage.
