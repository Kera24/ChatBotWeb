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
## TASK-065B3 Checklist Additions

- [ ] Composer sends only through iframe-owned services.
- [ ] Drafts, answers, citations, session tokens, and idempotency keys do not appear in parent postMessage payloads or host globals.
- [ ] Citation disclosure renders only validated public citation fields.
- [ ] Rate-limit and invalid-session recovery require explicit user action and do not retry storm.
- [ ] Focus remains inside the open iframe widget and Escape closes without clearing the draft.
## TASK-065B4 Release Additions

- [ ] Run `npm run widget:inspect:production` after a production widget build.
- [ ] Run `npm run widget:e2e:a11y` for representative accessibility release states.
- [ ] Run `npm run widget:e2e:visual` and review intentional visual baseline changes.
- [ ] Confirm drafts, answers, citations, and idempotency keys remain absent from parent globals, postMessage, console output, and host storage.
- [ ] Confirm production bundles exclude test harness globals, localhost mock hosts, fixture tokens, and mock response content.
## TASK-066B1 Production Delivery Foundation

TASK-066B1 implements repository-local, provider-neutral release artifacts, origin validation, cache/header policy, manifest/checksum generation, production inspection, and versioned-loader browser smoke coverage. It does not deploy production infrastructure. See `docs/04_Engineering/Widget_Production_Delivery_Security_and_Versioning.md` and `docs/06_Operations/Widget_Deployment_Runbook.md`.

## TASK-066B2 Real-Backend Isolation Additions

- [ ] Synthetic Alpha/Beta tenants are isolated at public credential, session, message, and retrieval boundaries.
- [ ] Alpha public session token is rejected against Beta widget context and vice versa.
- [ ] Alpha asks a Beta-only fact and receives no Beta citation, title, or quoted text.
- [ ] Beta asks an Alpha-only fact and receives no Alpha citation, title, or quoted text.
- [ ] Public config ETags and conditional requests do not serve cross-widget representations.
- [ ] Public widget APIs set no cookies in synthetic real-backend smoke.
- [ ] Pilot verification report redacts tokens, message bodies, answers, prompts, and credentials.

## TASK-066B3 Operational Security Additions

- [ ] Operational logs redact session tokens, Authorization headers, cookies, messages, answers, citation quotes, prompts, credentials, and raw public keys.
- [ ] Operational metric labels avoid raw session tokens, request IDs, public keys, origins, and message text.
- [ ] Host pages cannot enable pilot access or override kill switches.
- [ ] Existing sessions cannot bypass global message disablement.
- [ ] Pilot readiness reports contain no secrets, customer content, tokens, prompts, answers, or citation quotes.

## TASK-067B1 Admin Revisioning Coverage

Add security evidence for authenticated widget administration: tenant-scoped widget/revision reads, stale draft update rejection, draft changes not affecting public configuration, publish/rollback audit events, and cross-tenant denial for widget draft, publish, revision, and rollback APIs.

## TASK-067B2 Admin Origin, Key, And Embed Coverage

Add security evidence for authenticated origin/key/embed administration: exact-origin normalization, production localhost rejection, wildcard/path rejection, final active origin protection, public-key rotation cutover, old-key rejection, new-key public config resolution, cross-key ETag isolation, no arbitrary SDK URL or `latest`, snippet escaping, tenant-scoped origin/embed/key APIs, and audit events without full rotated keys.

## TASK-067B4 Security Checks

- Cross-tenant knowledge IDs are rejected.
- Preview grants cannot expose draft configuration through public endpoints.
- Installation evidence records no session token, message body, answer text, or visitor identity.
- Rollback target must belong to the same tenant/widget.
- Public retrieval uses the active published revision knowledge scope.

## TASK-067B5 Admin Security Gate

Controlled pilot administration now requires `npm run widget:admin:release:verify` in addition to the public widget pilot gates. This gate does not deploy production infrastructure and does not imply GA readiness.
