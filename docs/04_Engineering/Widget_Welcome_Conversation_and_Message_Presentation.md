# Widget Welcome, Conversation, and Message Presentation

Status: Implemented for TASK-065B2

## Scope

TASK-065B2 adds the first visual conversation experience inside the widget iframe. The implementation covers the configured welcome state, suggested questions, in-memory conversation entries, user/assistant message presentation, answer-state labels, retryable failure presentation, live announcements, and foundational scrolling.

The free-text composer, citation disclosure, full offline/session recovery workflows, Markdown rendering, telemetry, and visual regression suite remain deferred.

## State And Service Boundary

Preact components consume safe immutable snapshots and callbacks only. Components do not call `fetch`, do not access `sessionStorage`, and do not receive the public session token.

The runtime now creates:

- `ConversationStore`: framework-independent in-memory thread state.
- `ConversationOrchestrator`: UI-facing adapter that validates configured suggestions and calls the existing `MessageService`.

The existing iframe-owned API services continue to own config, session, message, idempotency, retry, and token storage behavior.

## Conversation Model

Conversation entries are in-memory only and are not written to browser storage.

Entry roles:

- `user`
- `assistant`
- `system`

User statuses:

- `sending`
- `sent`
- `failed`

Assistant statuses:

- `preparing`
- `answered`
- `fallback`
- `low_confidence`
- `failed`

System notice categories remain available for future recovery flows.

Store bounds:

- Maximum 100 entries.
- Maximum total content budget of 60,000 characters, trimming oldest entries first.

The store excludes session tokens, idempotency keys, provider/model metadata, tenant IDs, internal conversation IDs, and raw backend errors.

## Welcome State

The welcome state uses validated public configuration:

- Bot name.
- Welcome message.
- Suggested questions.
- Existing theme/design tokens.

Fallback copy is used when welcome text is missing. The welcome content is rendered as text nodes only and does not create a fake assistant message.

## Suggested Questions

Suggested questions are the only visual send mechanism in B2.

Rules:

- Suggestions come only from validated public configuration.
- Empty, too-long, duplicate, or unsafe-control-heavy suggestions are removed.
- Maximum visible count follows config and is capped at four.
- Buttons use native button semantics.
- Selecting a suggestion sends it directly.
- One active message request is allowed at a time.
- Repeated presses during an active send do not create duplicate message requests.

## Message Orchestration

Suggestion send flow:

1. User activates a configured suggestion.
2. A user entry appears immediately.
3. An assistant preparation entry appears.
4. The existing `MessageService` lazily creates a session if needed.
5. The existing message endpoint call uses the existing idempotency behavior.
6. The assistant entry resolves to answered, fallback, low-confidence, or failed.
7. Remaining session state updates through existing services.

Retries are shown only for safe retryable failures. Retry reuses the orchestrator's logical send metadata and does not expose idempotency keys.

## Answer-State Mapping

Backend answer states are mapped directly:

- `answered` -> standard assistant answer.
- `fallback` or `fallback_used` -> fallback answer label.
- `low_confidence` -> low-confidence label.
- `temporarily_unavailable` -> failed/unavailable presentation.

The UI does not infer confidence from wording.

## Plain-Text Rendering

Message text is rendered as text nodes only.

The UI does not:

- Use `dangerouslySetInnerHTML`.
- Parse HTML.
- Parse Markdown.
- Auto-linkify URLs.
- Render script, iframe, object, SVG, or image nodes from message text.

Excess control characters are stripped and excessive blank lines are visually bounded.

## Citations

Validated citations may be retained in iframe conversation entries, but B2 does not render citation disclosure. A small non-interactive “Sources available” placeholder is reserved when citations exist. Full citation UX remains TASK-065B3.

## Scrolling And Announcements

The conversation viewport auto-scrolls when the user is near the bottom. If the user has scrolled upward, new content exposes a `Jump to latest` control.

Live-region strategy:

- One hidden polite live region announces concise status changes.
- The full thread is not live.
- Preparation and answer-ready updates are announced once per state revision.
- Focus is not stolen when answers arrive.

## Accessibility

Implemented foundations:

- Welcome heading and conversation region.
- Suggestion button group.
- Message list semantics.
- User and assistant article labels.
- Preparation `role=status`.
- Retry buttons with visible text labels.
- Non-colour-only fallback and low-confidence labels.
- Reduced-motion support for the preparation indicator.
- Forced-colours borders for message and suggestion surfaces.

Final focus trap and composer focus behavior remain TASK-065B3.

## Tests

Added coverage for:

- Conversation store append/resolve/failure/bounds.
- Suggestion derivation and orchestration.
- Welcome and suggested questions.
- User/assistant/fallback/low-confidence/failed message presentation.
- Inert malicious plain-text rendering.
- Retry callback behavior.
- Real browser suggestion-send flow through loader and iframe.
- Lazy session creation on first suggestion.
- Double activation preventing duplicate message requests.
- Fallback and low-confidence browser presentation.
- Conversation memory preserved across close/open and not restored after iframe reload.

## Bundle Sizes

B2 production widget build:

- JS gzip: approximately 21.92 KB.
- CSS gzip: approximately 3.20 KB.

The SDK bundle remains materially unchanged and framework-free.
