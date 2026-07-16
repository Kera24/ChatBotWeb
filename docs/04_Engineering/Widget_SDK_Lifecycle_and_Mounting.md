# Widget SDK Lifecycle and Mounting

TASK-064B3 adds the browser-facing lifecycle runtime for the embeddable Yoranix widget SDK.

## Public API

The SDK exposes a bounded API through ESM exports and, in the browser bundle, `window.YoranixWidget`:

```ts
YoranixWidget.init(config)
YoranixWidget.open()
YoranixWidget.close()
YoranixWidget.toggle()
YoranixWidget.destroy()
YoranixWidget.isOpen()
YoranixWidget.isReady()
YoranixWidget.whenReady()
YoranixWidget.on(event, handler)
YoranixWidget.off(event, handler)
YoranixWidget.getState()
```

The API exposes version metadata and safe methods only. Internal controller objects are not returned to host pages.

## Auto Init

The IIFE bundle installs `window.YoranixWidget` if no unrelated global exists. If the current script includes a widget key, it auto-initialises once.

Supported attributes:

```html
<script
  src="https://widget.yoranix.com/sdk/v1/loader.js"
  data-widget-key="wpk_live_example"
  data-environment="production"
  data-initial-open="false"
  data-mount-mode="floating"
  data-locale="en-AU"
  async
></script>
```

Rejected by configuration validation: tenant IDs, session tokens, arbitrary production hosts, model/provider/prompt controls, Origin overrides, security-policy overrides, and arbitrary HTML/CSS/JavaScript.

## Lifecycle

Runtime states:

- `uninitialised`
- `validating`
- `mounting`
- `handshaking`
- `ready_closed`
- `ready_open`
- `degraded`
- `failed`
- `destroying`
- `destroyed`

`init` is idempotent for the same effective configuration. Conflicting initialisation rejects with a safe `duplicate_initialisation` error. `destroy` removes the iframe/container/listeners/timers and allows a clean future initialisation through the same public API.

## One Instance

MVP supports one widget instance per page. Duplicate loader execution reuses an existing Yoranix global if it was created by this SDK and refuses to overwrite unrelated globals.

## DOM Mounting

The SDK creates:

- one root container: `#yoranix-widget-root`
- one iframe: `#yoranix-widget-iframe`
- one structural style element: `#yoranix-widget-sdk-style`

Mounting uses DOM APIs, not `innerHTML`. Floating mode is implemented. Inline mode remains a validated contract for future work.

## Iframe Attributes

The SDK applies the B2 recommended iframe attributes:

- `sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"`
- `allow=""`
- `referrerpolicy="strict-origin-when-cross-origin"`
- `title="Yoranix chat widget"`
- `loading="lazy"`

The iframe URL contains only the public widget key, `parent_origin`, and bounded version hints. It never contains a session token, tenant ID, conversation ID, message, or secret.

## Handshake

The runtime flow is:

1. Validate config.
2. Resolve environment and hosts.
3. Build iframe URL.
4. Mount iframe.
5. Start B2 handshake.
6. Accept validated `iframe_ready` from the exact iframe origin/source.
7. Send `initialise` with non-secret payload.
8. Accept validated `widget_ready`.
9. Resolve `whenReady()`.

No public backend API call or storage access occurs.

## Commands And Acknowledgements

`open`, `close`, and `toggle` send protocol commands after readiness. The SDK updates open/closed state only after a validated `widget_state_changed` acknowledgement from the iframe. Command timeout returns a safe `command_timeout` error.

## Events

Supported events:

- `ready`
- `opened`
- `closed`
- `error`
- `destroyed`
- `state_changed`
- `degraded`

Host handler exceptions are isolated from SDK runtime state. Destroy clears handlers.

## Resize And Focus

The SDK accepts bounded `resize_request` messages and clamps dimensions to safe desktop/mobile bounds. On open it remembers the active host element and focuses the iframe after acknowledgement. On close it restores focus if the previous element is still connected.

## Debug

Debug logging is disabled by default and only active for validated development configuration. It never logs full widget keys, future session tokens, messages, or stack traces through public callbacks.

## Local Smoke Harness

`examples/widget-host/index.html` contains a small non-product host page with fake development values and manual controls. It makes no backend API calls.

Typical local flow:

```bash
npm run widget-sdk:build
npm run widget:build
npm run widget:dev
```

Serve `examples/widget-host/index.html` with any static file server and load the built SDK bundle for local manual checks.

## Current Exclusions

No public config/session/message API clients, session storage, final launcher styling, chat UI, message composer, telemetry, backend changes, CDN publishing, npm publishing, streaming, or Markdown rendering are implemented in this task.

## Widget Iframe API Client And Session Storage

TASK-064B4 adds iframe-owned public API access inside `apps/widget`.

The iframe now loads validated public configuration after the secure handshake, caches it with ETag support, restores anonymous sessions from iframe-origin `sessionStorage`, falls back to memory storage when needed, and exposes internal services for first-message session creation and idempotent message sends.

The host SDK still does not call public APIs, store sessions, send messages, or receive public session tokens. The final visual chat interface is still not implemented.
