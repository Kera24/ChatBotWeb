# Widget Composer, Citations, and Recovery

TASK-065B3 makes the iframe widget usable for normal text conversations while preserving the SDK/API security boundary.

## Composer

The composer is a Preact UI layer over the framework-independent conversation orchestrator. Components do not call `fetch`, read session storage, or receive the public session token.

Implemented behavior:

- Multiline textarea with a visible `Message` label.
- Send button with accessible name `Send message`.
- Enter submits and Shift+Enter inserts a newline.
- IME composition prevents accidental Enter submission.
- Boundary whitespace is trimmed on submission; internal line breaks are preserved.
- Empty, whitespace-only, unsupported control-character, and over-limit messages are rejected locally before service calls.
- The public-message limit is `4000` characters in the iframe UI, aligned with the current message service guard.
- Character count appears near/over the limit and no silent truncation occurs.
- Drafts are iframe memory only and are not stored in `sessionStorage`, `localStorage`, cookies, postMessage, or host state.

## Message Flow

Suggestions and free-text messages share the same `ConversationOrchestrator` path:

1. Validate UI input.
2. Append user entry and assistant preparation entry.
3. Use the existing `MessageService` for session creation, idempotency, request retry, response validation, and token isolation.
4. Resolve the assistant entry with the validated public response.
5. Fail safely with retry only when the safe error policy allows explicit recovery.

The MVP concurrency policy remains one active message request at a time.

## Citations

Citation disclosure uses only the public citation contract returned by the backend:

- `citation_index`
- `source_title`
- `source_type`
- optional `page_number`
- optional `section_title`
- optional `quoted_text`

The UI renders a compact `Sources (n)` disclosure below answered or low-confidence assistant messages. It does not parse inline citation markers, invent citations, render similarity scores, expose internal IDs, or create external links because the current public contract does not include a validated public citation URL.

Fallback answers do not display a source disclosure.

## Privacy Footer

The footer renders configured privacy notice text where available, otherwise a platform-safe reminder to avoid sharing sensitive personal information. Privacy and terms URLs are rendered only when they are valid HTTPS URLs without userinfo. Links use `target="_blank"` and `rel="noopener noreferrer"`.

## Connectivity

The iframe uses `navigator.onLine` plus `online`/`offline` events as advisory state only. Offline mode:

- Shows a conversation-level notice.
- Keeps the textarea editable for drafting.
- Disables sending.
- Does not queue messages.
- Requires explicit send after reconnection.

Request failures remain authoritative through the existing API client and message service.

## Session And Rate Recovery

Invalid or expired sessions are cleared by `MessageService`/`SessionService`. The UI does not silently resend. It displays a session-ended notice and exposes an explicit retry action for recoverable failed sends. Session-limit state disables sending and preserves the visible conversation.

Rate-limit responses use safe `retryAfterSeconds` values to show wait guidance and disable sending for the bounded interval. The screen-reader live region announces the start and availability state, not every tick.

Remaining-message warnings appear only when `remainingMessages <= 3`.

## Focus And Keyboard

The open panel has a local focus boundary inside the iframe. Tab and Shift+Tab cycle through enabled controls, Escape closes the widget, async answer arrival does not steal focus, and first open focuses the panel heading rather than the textarea to avoid opening the mobile keyboard immediately.

## Security Boundaries

- Session tokens stay inside iframe services/storage.
- Drafts, answers, citations, idempotency keys, and session tokens never cross postMessage.
- Message text is rendered as text nodes only.
- No Markdown or HTML rendering is implemented.
- Citation text is bounded and rendered as inert text.
- Test hooks remain test-mode only.

## Commands

```bash
npm run widget:test
npm run widget:lint
npm run widget:build
npm run widget:e2e:chromium
npm run widget:e2e:extended
npm run verify
```

## Exclusions

Still excluded: streaming, conversation history persistence, reload restoration of messages, draft storage, Markdown, uploads, voice, lead capture, human handoff, telemetry, analytics, public SDK send APIs, and backend changes.
