# Widget Iframe API Client and Session Storage

TASK-064B4 adds the iframe-owned public API foundation for the embeddable widget.

## Ownership Boundary

Only `apps/widget` calls public widget APIs:

- `GET /api/v1/widget/{public_key}/config`
- `POST /api/v1/widget/{public_key}/sessions`
- `POST /api/v1/widget/{public_key}/messages`

The host SDK does not call these endpoints and does not receive API responses. Public session tokens are never sent through postMessage, iframe URLs, host callbacks, SDK runtime state, logs, telemetry, or public state snapshots.

## API Host Resolution

The iframe resolves the API host from the validated handshake environment using the shared SDK environment resolver.

- Development may use localhost defaults.
- Staging and production require HTTPS hosts.
- Production does not accept arbitrary host overrides from the page.
- URLs are normalised and reject userinfo, fragments, and unsafe schemes.

## Response Validation

The iframe validates every network response before it enters runtime state.

Validation covers required fields, schema versions, timestamps, bounded strings and arrays, safe colours, HTTPS URLs, and public citation shape. Config and message responses are rejected if they contain session-token fields or detectable tenant/internal identifiers.

The implementation uses small manual validators instead of a large schema dependency.

## Configuration Loading And Cache

After the secure iframe handshake validates `initialise`, the iframe loads public configuration before sending `widget_ready` to the loader.

Config caching uses iframe-origin `sessionStorage` with memory fallback through tests and service injection. Cached records are scoped by widget key and environment and include:

- validated public config
- ETag
- cached timestamp
- cache schema version

`If-None-Match` is sent when a cached ETag exists. A `304 Not Modified` response is accepted only when a previously validated cache record exists. Corrupted or incompatible cached records are discarded.

Config loading never creates a public session.

## Session Storage

The iframe stores anonymous public sessions through a `SessionStore` abstraction.

Implementations:

- `BrowserSessionStore`: iframe-origin `sessionStorage`
- `MemorySessionStore`: fallback when storage is blocked or unavailable

Stored fields are limited to:

- `sessionToken`
- `expiresAt`
- `absoluteExpiresAt`
- `remainingMessages`
- `configurationVersion`
- `createdAt`
- `schemaVersion`

The iframe does not use `localStorage`, cookies, IndexedDB, host-page storage, or URL parameters for sessions.

## Session Creation Strategy

TASK-064B4 uses first-message session creation.

Opening the non-visual shell does not create a session. The message service creates a session lazily before the first logical message send and coalesces concurrent creation requests into one in-flight promise. This avoids minting sessions for visitors who only load or open the placeholder shell.

Local expiry checks are advisory. The backend remains authoritative and invalid-session responses clear the stored token without silently resending the original message.

## Message Service

`MessageService` is internal to the iframe and is not exposed to the host SDK.

It:

1. Validates and normalises the local message.
2. Ensures an active session exists.
3. Generates a cryptographically random idempotency key.
4. Calls the public message endpoint with `credentials: omit`.
5. Validates the public response.
6. Updates token-free state with remaining messages and expiry.

The service preserves the same idempotency key across bounded retry attempts for the same logical send. It does not retry non-retryable validation, abuse, quota, rate-limit, or idempotency-conflict responses.

## State Store

The framework-free state store exposes immutable snapshots for future UI work:

- bootstrap status
- config status and validated public config
- session status, expiry, remaining-message count, and configuration version
- message request status and last safe response
- last safe error

State snapshots never include the raw session token.

## Retry And Errors

Network requests use injected `fetch`, request timeouts, `AbortController`, JSON content-type enforcement, and `credentials: omit`.

Safe iframe error codes include configuration, session, message, storage, random, network, timeout, rate-limit, quota, and incompatible-response failures. Errors do not include backend stack traces, tenant IDs, raw public keys, session tokens, request bodies, model/provider metadata, or policy thresholds.

## Current Exclusions

This task does not add:

- final launcher or chat UI
- message list or composer
- Markdown rendering
- conversation-history UI
- streaming
- telemetry
- lead capture
- host-page `sendMessage`
- React
- backend changes

## Test Commands

```bash
npm run widget:test
npm run widget:lint
npm run widget:build
npm run verify
```