# Widget Security Test Checklist

Use this checklist before releasing widget SDK or iframe changes.

## Loader And Iframe

- [ ] SDK creates one iframe for one widget instance.
- [ ] Duplicate identical init reuses the existing runtime.
- [ ] Conflicting init is rejected safely.
- [ ] Iframe URL contains no session token, tenant ID, conversation ID, message, or secret.
- [ ] Iframe sandbox excludes top navigation, camera, microphone, geolocation, downloads, and clipboard permissions.
- [ ] Iframe title and shell status semantics are present.

## postMessage

- [ ] `targetOrigin` is never `*`.
- [ ] Parent validates iframe origin and `event.source`.
- [ ] Iframe validates parent origin and `event.source`.
- [ ] Wrong protocol/version/source messages are rejected or ignored safely.
- [ ] Token-like and tenant-like fields do not cross postMessage.
- [ ] Host cannot request message sending through public SDK protocol.

## API Ownership

- [ ] Config/session/message API calls occur only inside the iframe.
- [ ] Host SDK has no public `sendMessage` API.
- [ ] Config loads before `widget_ready`.
- [ ] Sessions are not created during page load or config load.
- [ ] First message creates or restores the session lazily.
- [ ] Idempotency keys are generated inside the iframe and are not logged.

## Token Isolation

- [ ] Session token is absent from host globals, SDK public API, parent DOM, iframe URL, postMessage, console, host storage, localStorage, and cookies.
- [ ] Session token is present only in iframe-origin `sessionStorage` or private in-memory state and the required message request body.
- [ ] Invalid/expired session clears iframe storage and does not silently resend a message.

## Browser Policy

- [ ] CORS uses browser Origin and approved headers only.
- [ ] Cookies and credentials are not sent.
- [ ] Supported CSP allows loader and iframe; blocked CSP fails safely.
- [ ] Closed widget does not block host-page interaction.
- [ ] Resize requests remain bounded on desktop and mobile.
- [ ] Console output does not include full widget keys, tokens, idempotency keys, messages, answers, citations, raw origins, or backend bodies.