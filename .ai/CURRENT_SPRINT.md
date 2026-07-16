# Current Sprint

Current phase: Sprint 3D - Embeddable Widget
Current task: TASK-064B4 - Widget Iframe API Client and Session Storage

## Active Objective

Implement iframe-owned public config, session, and message API foundations with token-isolated session storage and internal state/services for the future widget UI.

## Guardrails

- Public config/session/message API calls must stay inside `apps/widget`.
- Public session tokens must not enter the host page, SDK runtime state, iframe URL, postMessage payloads, logs, telemetry, or public state snapshots.
- Do not implement the final launcher, chat panel, message list, composer, rich message rendering, conversation-history UI, lead capture, telemetry, React, backend changes, or host-page `sendMessage` API.
- Config loads after handshake and before `widget_ready`; config load must not create a session.
- Current session strategy is first-message creation, not page-load or open creation.

## Definition Of Done

- Iframe API client validates public config/session/message responses.
- Config cache uses iframe-origin storage with ETag/304 support and safe corruption handling.
- Session storage uses `sessionStorage` with memory fallback and stores only approved fields.
- Message service uses secure idempotency keys and bounded retry without exposing tokens.
- Token-free state snapshots are available for future UI work.
- Tests cover API ownership, config cache, session storage, lazy session creation, idempotency, and postMessage token isolation.