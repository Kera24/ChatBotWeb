# Dashboard Conversation History

Version: 0.1
Status: Implemented

## Routes

- `/conversations` lists tenant-scoped conversation summaries.
- `/conversations/[conversationId]` shows one conversation with ordered messages, citations, and assistant execution details.

These are dashboard routes only. They do not implement the public widget, public chat, production authentication, analytics aggregation, export, deletion, or conversation search.

## Tenant Development Configuration

The current frontend uses explicit development-only tenant context:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID`
- `NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID`
- `NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL`
- `NEXT_PUBLIC_DEVELOPMENT_ROLE`

The UI shows a missing-configuration state if organisation or workspace IDs are absent. These values are temporary placeholders until production authentication and tenant selection exist.

## API Client Structure

Dashboard API code lives in `apps/web/lib/api/`:

- `client.ts` centralises `fetch`, base URL handling, response envelopes, and development headers.
- `errors.ts` maps 401, 403, 404, 409, 422, server, unknown, and network failures to typed UI states.
- `types.ts` defines conversation response types.
- `conversations.ts` exposes typed conversation list/detail functions.

Development auth headers are isolated in `apps/web/lib/auth/development-session.ts`. Public-widget clients must remain separate and must not reuse dashboard headers.

## UI States

The conversation history UI includes:

- loading states through Next route loading files
- empty state for workspaces with no conversations
- access-denied state for 403 responses
- missing tenant configuration state
- retryable error state for network and API failures
- pagination controls with previous/next links
- status/channel filters

## Privacy Exclusions

The UI displays user and assistant message content for dashboard review. It intentionally does not display:

- anonymous or external user identifiers
- raw system prompts or rendered prompts
- provider raw metadata
- message metadata JSON
- secrets, stack traces, or hidden internal fields

Technical details are limited to model/provider keys, prompt identity, token usage, estimated cost, latency, finish reason, and safe error code.

## Expressionism Design Application

The screen uses large expressive page typography, a high-contrast conversation count panel, visible state badges, and strong message/citation rhythm. Trust-critical information remains dense, legible, and operational: filters, source citations, answer states, costs, latency, and errors are explicit.

## Local Testing

Run:

```bash
npm run web:lint
npm run web:build
```

Full repository verification:

```bash
npm run api:test
npm run verify
```

A frontend unit test runner is not yet installed. Adding Vitest or Jest would be a separate foundation decision; this task relies on strict TypeScript, ESLint, and Next build verification.

## Temporary Auth Limitation

The development headers are not production authentication. They exist only to exercise backend RBAC and tenant isolation during local development.
