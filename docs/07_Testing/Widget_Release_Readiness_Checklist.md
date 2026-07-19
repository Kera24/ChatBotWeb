# Widget Release Readiness Checklist

Use this checklist before approving the embeddable widget for a controlled pilot or wider release.

## Build And Packaging

- [ ] `npm run widget:install` completed.
- [ ] `npm run widget:test` completed.
- [ ] `npm run widget:lint` completed.
- [ ] `npm run widget:build` completed.
- [ ] `npm run widget-sdk:test` completed.
- [ ] `npm run widget-sdk:lint` completed.
- [ ] `npm run widget-sdk:build` completed.
- [ ] `npm run widget:inspect:production` completed after a production widget build.
- [ ] `npm run widget:bundle:check` completed within budget.

## Browser Verification

- [ ] Required Chromium suite passed.
- [ ] Accessibility smoke suite passed.
- [ ] Visual regression suite passed or intentional baseline updates were reviewed.
- [ ] Extended Firefox/WebKit suite passed or named browser limitations were documented.
- [ ] Failure traces/screenshots contain only fake test data.

## Responsive And Visual

- [ ] Desktop panel remains bounded at 1920x1080, 1440x900, 1280x720, and 1024x768.
- [ ] Tablet portrait and landscape remain usable.
- [ ] Mobile 390x844, 375x667, 360x640, 320x568, and landscape remain usable.
- [ ] Composer remains reachable above the virtual keyboard where supported.
- [ ] No horizontal overflow occurs with long content.
- [ ] Launcher and close controls are always reachable.
- [ ] Customer-branding extremes preserve contrast and focus visibility.
- [ ] Reduced-motion mode remains functional.
- [ ] Forced-colours/high-contrast mode remains understandable.

## Accessibility

- [ ] Keyboard-only open, send, citation disclosure, retry, privacy link, and close flows work.
- [ ] Focus is contained only while the panel is open.
- [ ] Focus is restored safely on close/destroy.
- [ ] Composer validation is associated with the textarea.
- [ ] Status and error announcements are concise and non-duplicative.
- [ ] Message thread is not marked as a continuous live region.
- [ ] Controls meet target-size requirements.
- [ ] Manual assistive-technology review is scheduled before GA.

## Security

- [ ] Session token is absent from parent page, postMessage, iframe URL, DOM attributes, console, localStorage, and cookies.
- [ ] Drafts, messages, answers, citations, idempotency keys, and backend bodies do not cross to the host SDK.
- [ ] Iframe owns config/session/message API calls.
- [ ] postMessage validates protocol, version, origin, and source.
- [ ] No wildcard targetOrigin is used after bootstrap.
- [ ] Plain text rendering remains inert for HTML/Markdown-like payloads.
- [ ] Citation URLs, if present in the future, are HTTPS-only and validated.
- [ ] Production bundle excludes test hooks, test hosts, fixture tokens, mock content, and normal console logging.
- [ ] SDK bundle remains framework-free.

## CSP, Sandbox, And CORS

- [ ] Customer CSP includes loader script host.
- [ ] Customer CSP includes iframe host in `frame-src` or `child-src`.
- [ ] Widget/API origin is included in `connect-src` only where required by iframe execution.
- [ ] No `unsafe-eval` is required.
- [ ] Iframe sandbox attributes match the documented minimum.
- [ ] Permissions policy does not request microphone, camera, geolocation, clipboard, downloads, or top navigation.
- [ ] Backend CORS allows only configured origins and does not require credentials.

## Operational Readiness

- [ ] Production widget host, iframe host, and API host are configured.
- [ ] Versioned loader and iframe deployment/rollback plan exists.
- [ ] Real-backend smoke test plan exists.
- [ ] Monitoring/alerting plan exists for config/session/message availability.
- [ ] Known limitations are communicated to pilot customers.
- [ ] Rollback command/procedure is documented.

## Release Classification

- [ ] Controlled pilot approved.
- [ ] General availability approved.
- [ ] Blocked pending named issues.
## TASK-066B1 Production Delivery Foundation

TASK-066B1 implements repository-local, provider-neutral release artifacts, origin validation, cache/header policy, manifest/checksum generation, production inspection, and versioned-loader browser smoke coverage. It does not deploy production infrastructure. See `docs/04_Engineering/Widget_Production_Delivery_Security_and_Versioning.md` and `docs/06_Operations/Widget_Deployment_Runbook.md`.
