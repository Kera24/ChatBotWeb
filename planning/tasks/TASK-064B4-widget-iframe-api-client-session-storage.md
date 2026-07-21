# TASK-064B4 - Widget Iframe API Client and Session Storage

Status: In progress

Scope:
- Implement iframe-owned public API access for widget config, session creation, and messages.
- Keep session tokens inside the iframe origin only.
- Add response validation, session storage fallback, idempotency keys, retry behaviour, and API state foundation.

Constraints:
- No final visual chat UI.
- No host-page message API.
- No backend changes.
- No session token in postMessage, iframe URL, SDK runtime state, logs, or public state snapshots.
