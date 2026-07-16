# Current Sprint

Current phase: Sprint 3D - Embeddable Widget
Current task: TASK-064B5 - Widget Browser Integration and Security Tests

## Active Objective

Create browser-level integration and security tests for the embeddable widget loader, iframe shell, postMessage boundary, iframe-owned API calls, token isolation, storage, lifecycle, CORS/CSP, and hostile-host scenarios.

## Guardrails

- Do not implement the final launcher, chat panel, composer, message thread, rich citations, visual branding system, conversation-history UI, lead capture, telemetry, analytics, streaming, new backend endpoints, or host-page `sendMessage` API.
- Browser tests may use test-mode iframe hooks only when compiled with Vite `test` mode.
- Test hooks must not expose session tokens or become production host APIs.
- Production verification must rebuild the normal widget artifact after test-mode e2e runs.

## Definition Of Done

- Chromium browser tests run real built SDK and iframe artifacts across separate local origins.
- Token isolation, postMessage validation, storage, CORS, CSP, sandbox, lifecycle, responsive, focus, accessibility shell, and safe logging checks are covered.
- Root scripts and CI install and run required Chromium browser tests.
- Extended Firefox/WebKit command is documented separately.