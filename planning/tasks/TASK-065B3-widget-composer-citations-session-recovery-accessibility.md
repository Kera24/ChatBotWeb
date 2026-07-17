# TASK-065B3 - Widget Composer, Citations, Session Recovery, Offline Behaviour, and Accessibility Completion

Status: Implemented
Sprint: Sprint 3E - Widget Experience

## Objective

Implement the functional conversation layer for the iframe widget: free-text composer, citation disclosure, recovery states, privacy/footer presentation, connectivity handling, and keyboard/focus accessibility foundations.

## Scope Implemented

- Multiline free-text composer with local validation.
- Enter-to-send and Shift+Enter newline behavior with IME guard.
- Shared orchestration path for suggestions, custom messages, and explicit retry.
- In-memory-only draft and conversation state.
- Citation disclosure using validated public citation fields only.
- Privacy/footer presentation with safe HTTPS links.
- Offline/reconnecting advisory state using iframe-local browser events.
- Rate-limit wait presentation using safe retry-after values.
- Session-ended and invalid-session recovery requiring explicit user retry.
- Remaining-message warning near the session cap.
- Panel focus containment, Escape close behavior, labelled controls, and live-region status announcements.

## Guardrails

- No backend changes.
- No SDK public message API.
- No session token in Preact state, DOM attributes, postMessage, logs, or conversation entries.
- No idempotency key exposed in UI state.
- No Markdown, raw HTML, streaming, file upload, voice, telemetry, lead capture, or history persistence.
- Answers and citations stay inside the iframe.

## Verification Expectations

- Widget unit/component tests cover composer validation, IME behavior, citation disclosure, rate/session notices, and custom-message orchestration.
- Browser tests cover real loader-to-iframe custom sends, citation disclosure, rate limiting, invalid-session recovery, and token/security regressions.
- Existing SDK, API, web, widget, and browser security suites remain passing.

## Follow-Up

TASK-065B4 should focus on responsive/mobile hardening, motion polish, visual regression, broader accessibility/security browser coverage, and performance optimisation.
