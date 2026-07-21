# ADR-0014: Widget SDK and Iframe Delivery

Status: Proposed
Date: 2026-07-15

## Context

The platform now has public widget configuration, anonymous session creation, public message/RAG execution, and output sanitisation. The next product boundary is how customer websites embed the future visual chat widget.

The embed must work on thousands of customer sites, avoid dashboard authentication, preserve tenant isolation, prevent public session token leakage, and allow gradual SDK upgrades. Customer pages may have hostile or fragile CSS/JavaScript, strict CSP, SPA navigation, browser extensions, and duplicate script loads.

The loader SDK and the visual chat application are separate components. The SDK should bootstrap and control the widget shell; the visual iframe app should own rendering and public API calls.

## Decision

Use a small versioned loader SDK plus a platform-hosted sandboxed iframe.

The iframe owns public config/session/message API calls and stores anonymous public session tokens in iframe-origin `sessionStorage` with in-memory fallback. Session tokens must never enter the host-page JavaScript context, postMessage payloads, iframe URLs, telemetry, or host callbacks.

The loader SDK owns installation parsing, iframe creation, sandbox/allow attributes, lifecycle state, strict versioned postMessage transport, open/close/toggle/destroy APIs, event subscription, bounded resizing, and safe failure fallback.

The postMessage protocol uses a strict envelope with protocol name, version, message ID, type, source, payload, and timestamp. Loader and iframe validate exact origins, source window, protocol version, message type, and bounded payloads.

## Alternatives Considered

### A. Direct DOM Widget

Pros:

- Simple initial implementation.
- Easy host-page styling hooks.
- No iframe focus/postMessage complexity.

Cons:

- Host CSS and JavaScript can interfere with widget state and rendering.
- Public session token would be harder to keep out of host-page JS context.
- Larger XSS blast radius.
- More CSP and namespace conflicts.

Rejected.

### B. Web Component With Shadow DOM

Pros:

- Better style isolation than direct DOM.
- More integrated accessibility and layout.
- Can be distributed as a package.

Cons:

- Still shares host JavaScript context and storage.
- Token isolation remains weaker than iframe.
- Browser/polyfill and host-framework interactions add risk.

Rejected for MVP; may become an optional wrapper later.

### C. Sandboxed Iframe

Pros:

- Strong CSS isolation.
- Stronger containment for widget XSS/rendering mistakes.
- Independent app deployment and rollback.
- Session token can stay in iframe origin storage.
- Clear postMessage and CORS trust boundaries.

Cons:

- More complex focus management and accessibility coordination.
- Requires CSP `frame-src` allowlisting.
- Requires strict postMessage protocol and version negotiation.
- Responsive sizing and mobile keyboard behavior need care.

Chosen.

### D. npm Package Only

Pros:

- Good for modern app teams.
- Strong version pinning.
- Can integrate with framework build systems.

Cons:

- Poor default for simple customer website install.
- Slower adoption for non-engineering customers.
- Does not itself solve token isolation.

Rejected as the only MVP path. Future npm wrapper can call the same loader/runtime.

### E. Iframe Plus Optional npm Wrapper

Pros:

- Secure default install path.
- Future developer ergonomics.
- One shared protocol and iframe app.

Cons:

- Requires multiple artifacts and compatibility testing.

Chosen direction.

## Consequences

Positive:

- Public session tokens stay out of host-page JavaScript.
- Widget rendering and CSS are isolated from customer sites.
- Loader can remain dependency-light and stable.
- Iframe app can evolve independently from the loader.
- Dedicated widget origin improves CSP and deployment control.
- Future npm wrapper can preserve the same security model.

Trade-offs:

- postMessage protocol must be carefully versioned and tested.
- Accessibility requires explicit focus transfer and iframe title semantics.
- Customer CSP documentation is required.
- Combining `allow-scripts` and `allow-same-origin`, if needed, must be treated as a deliberate risk accepted only on a dedicated widget origin.
- Host pages can still hide, overlay, or remove the iframe because the host page controls its own DOM.

## Required Controls

- Loader and visual widget remain separate components.
- Iframe owns config/session/message API calls.
- Session token never crosses postMessage and is never placed in URL or parent storage.
- Backend Origin validation remains authoritative.
- postMessage validates exact origin, source, protocol, version, type, and payload size.
- No wildcard targetOrigin after bootstrap.
- MVP supports one widget instance per page.
- SDK exposes only open/close/toggle/destroy/isOpen/on/off/init.
- Production installs cannot override iframe/API origins.
- Loader uses semantic versioning; protocol versioning is separate.
- Pinned immutable loader URLs may use SRI.
- CSP requirements are documented.

## Implementation Split

- `TASK-064B1` - SDK package/build foundation.
- `TASK-064B2` - Iframe shell and secure handshake.
- `TASK-064B3` - SDK lifecycle, mounting, and public API.
- `TASK-064B4` - Iframe API client and session storage.
- `TASK-064B5` - Browser integration/security tests.
- `TASK-065A` - Widget UI and Interaction Architecture.
- `TASK-065B` - Widget UI Implementation.

## Non-Goals

This ADR does not implement:

- SDK package.
- Loader script.
- Iframe route/page.
- postMessage runtime code.
- Visual chat UI.
- Build tooling.
- npm publishing.
- Public history.
- Analytics or telemetry backend.
- Lead capture.
- Backend endpoint changes.

## Related Documents

- `implementation-pack/02_Architecture/09_Embeddable_Widget_SDK_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0011-public-widget-session-endpoint.md`
- `docs/adr/0012-public-widget-configuration-delivery.md`
- `docs/adr/0013-public-widget-message-rag-boundary.md`
- `planning/tasks/TASK-064A-embeddable-widget-sdk-architecture.md`