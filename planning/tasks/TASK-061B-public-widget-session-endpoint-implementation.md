# TASK-061B: Public Widget Session Endpoint Implementation

Status: Complete
Type: Implementation task
Sprint: Sprint 3C - Public Channels

## Objective

Implement the first public platform endpoint:

```text
POST /api/v1/widget/{public_key}/sessions
```

The endpoint creates an anonymous public session only. It does not create conversations, accept chat messages, invoke retrieval, invoke RAG, invoke AI Core, expose widget branding, or expose internal configuration data beyond approved session capabilities.

## Implemented Scope

- Added a separate public widget router at `apps/api/app/api/v1/public_widget.py`.
- Registered `POST` and `OPTIONS` for `/api/v1/widget/{public_key}/sessions` under the `public-widget` tag.
- Added the first production-facing widget channel adapter at `apps/api/app/access/channels/widget.py`.
- Added public widget session request/response schemas at `apps/api/app/schemas/public_widget.py`.
- Wired the route through `PublicAccessGateway` in `session_creation` mode.
- Added gateway support for session-creation enrichment so published widget configuration can gate session creation and shape safe capabilities before the session is created.
- Added narrowly scoped dynamic CORS handling for this route only.
- Added safe widget endpoint errors and widget session events.
- Added route tests for success, credential/config eligibility, request rejection, Origin/CORS, rate limiting, privacy exclusions, no conversation creation, and route boundary preservation.

## Explicit Non-Goals Preserved

- No public widget config endpoint.
- No public widget message endpoint.
- No RAG, retrieval, provider, or AI Core invocation.
- No conversation or chat-message creation.
- No widget SDK/UI.
- No streaming, lead capture, feedback, domain ownership verification, cookies, global permissive CORS, production analytics, or hard idempotency store.
- No database migration.

## Acceptance Criteria

- [x] Public route is visually separate from dashboard routes.
- [x] Empty request body is accepted.
- [x] Tenant IDs, conversation IDs, message fields, PII, origin/IP body fields, and policy/model/provider overrides are rejected.
- [x] Dashboard development headers and dashboard bearer tokens are rejected.
- [x] Active `widget_public_key`, active tenant/workspace, allowed Origin, passing rate limits, and published widget configuration are required.
- [x] `widget_session_create` is used for POST rate limiting.
- [x] Dynamic CORS echoes only the validated Origin and never uses wildcard or cookies.
- [x] Response returns only the session token, expiry, message limits, configuration version, safe capabilities, and request ID.
- [x] No conversation row is created.
- [x] Existing Public Access, origin/rate/session foundations remain passing.