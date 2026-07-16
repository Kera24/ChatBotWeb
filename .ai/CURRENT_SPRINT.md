# Current Sprint

Current phase: Sprint 3D - Embeddable Widget
Current task: TASK-064B2 - Iframe Shell and Secure Handshake

## Active Objective

Implement the non-visual iframe shell, strict versioned postMessage contracts, secure bootstrap handshake, iframe-origin validation, parent-origin validation, and lifecycle-ready communication foundation.

## Guardrails

- Do not call public config/session/message APIs.
- Do not store session tokens or use browser storage.
- Do not implement the visual launcher, chat panel, message list, composer, or final widget UI.
- Do not expose the final `window.YoranixWidget` lifecycle API.
- Do not add telemetry, backend changes, CDN deployment, SRI generation, or React.
- Keep postMessage payloads free of session tokens, tenant IDs, API credentials, raw backend responses, and message content.

## Definition Of Done

- `apps/widget` exists as a dedicated Vite TypeScript iframe app.
- Shared protocol contracts live in the SDK package and are consumed by the iframe app.
- SDK-side iframe URL builder and handshake controller validate origin, source, version, type, payload size, timeout, and destroy behavior.
- Iframe shell validates parent origin using URL parameter, referrer, and incoming message origin.
- Minimal accessible shell renders loading/ready/unavailable states only.
- Root verify and CI include widget app checks.
- Documentation is updated.
