# TASK-063B1 - Public Message Preparation and Idempotency

## Objective

Implement the internal preparation foundation for future public widget messages without exposing a public message route and without invoking retrieval, RAG, AI Core, providers, abuse services, or cost-control services.

## Scope

- Add persistent `public_message_requests` idempotency records.
- Add strict internal message and metadata validation.
- Add HMAC idempotency-key storage and canonical request hashing.
- Add a preparation service that validates a public session, resolves idempotency state, creates or attaches a tenant-scoped widget conversation, and consumes one message slot for new work.
- Add an internal Public Access Gateway `message_send` extension point only.
- Preserve existing public config and session endpoints.

## Non-Goals

- No `POST /api/v1/widget/{public_key}/messages` route.
- No public HTTP schemas for messages.
- No RAG, retrieval, AI Core, provider execution, streaming, output sanitisation, abuse detection, moderation, cost/quota enforcement, or widget UI.
- No public request creates user or assistant chat messages in this task.

## Implementation Notes

- `Idempotency-Key` is required for future message sends, bounded, header-safe, and stored only as a keyed HMAC.
- Request hashes use canonical JSON over the canonical message, bounded metadata, internal public-session reference, and schema version.
- Same key plus same request in `processing` returns `request_in_progress`; same completed request returns the stored safe response snapshot; same key plus different request returns `idempotency_conflict`.
- Slot consumption occurs only for a new request after validation, session validation, idempotency ownership, and conversation resolution.
- Completed, in-progress, conflicting, or invalid requests do not consume another slot.
- If preparation fails after processing ownership, the idempotency record is marked `failed`; if the slot was already consumed it remains consumed.

## Acceptance Criteria

- `public_message_requests` model and migration exist.
- Internal contracts, validation, idempotency repository/service, and preparation service exist.
- Gateway has only an internal `message_send` preparation extension point.
- Existing public endpoints are unchanged and no message route is added.
- Unit tests cover validation, idempotency states, slot consumption, and conversation attachment.
- Documentation and sprint context are updated.
