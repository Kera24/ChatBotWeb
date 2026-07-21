# Public Message Preparation and Idempotency

TASK-063B1 adds the internal preparation foundation for future public widget messages. It does not expose a public message endpoint and does not call retrieval, RAG, AI Core, providers, abuse services, or cost-control services.

## Model

`public_message_requests` stores one idempotency record per public session and idempotency key hash.

Key fields:

- `organisation_id`, `workspace_id`, `credential_id`, `public_session_id`
- `idempotency_key_hash`, never the plaintext key
- `request_hash`, derived from canonical public inputs
- `status`: `received`, `processing`, `completed`, `failed`
- optional `user_message_id`, `assistant_message_id`, and safe `response_snapshot_json`
- `error_code`, lifecycle timestamps, `expires_at`, safe metadata, and `deleted_at`

The table has tenant/workspace indexes, credential/session/status/expiry/deleted indexes, and a unique constraint on `public_session_id + idempotency_key_hash`.

## Idempotency

Future public widget message requests must provide an `Idempotency-Key`. TASK-063B1 accepts only bounded URL/header-safe keys. The key is HMAC-SHA256 hashed with `PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET` before storage and is never logged or emitted.

Resolution rules:

- New key: create a `received` record, then transition to `processing` for the preparation owner.
- Same key and same request hash while processing: return `request_in_progress` without consuming another message slot.
- Same key and same request hash when completed: return the stored safe response snapshot.
- Same key and different request hash: return `idempotency_conflict` without consuming a slot.
- Failed records are terminal for the MVP; clients must use a new key.

## Request Hashing

The request hash is a SHA-256 digest of canonical JSON containing:

- schema version
- canonical message
- bounded safe metadata
- internal public-session reference

It excludes raw session tokens, raw public keys, Origin, IP address, request IDs, trace IDs, and timestamps.

## Validation

The message validator:

- trims surrounding whitespace
- normalises CRLF and CR to LF
- rejects empty messages, NUL bytes, unsafe control characters, excessive character count, and excessive UTF-8 byte count
- preserves meaningful Unicode
- bounds metadata item count, key length, and scalar value length
- rejects tenant, conversation, model, provider, prompt, retrieval, context, token, identity, email, phone, origin, IP, policy, and capability override fields

This is input validation only. Abuse classification and moderation remain future tasks.

## Preparation Flow

The internal preparation service performs:

1. Validate message and metadata.
2. Validate the public session through `PublicSessionService` with tenant, credential, channel, environment, policy, and canonical-Origin binding.
3. Resolve idempotency state.
4. Return completed or in-progress duplicates without consuming a slot.
5. For new work, transition the idempotency record to `processing`.
6. Resolve the existing session conversation or create one tenant-scoped `chat_session` with channel `widget`.
7. Attach the conversation to the public session atomically through `PublicSessionService`.
8. Atomically consume one message slot.
9. Return `PreparedPublicMessage` for future abuse/cost/RAG stages.

No user or assistant `chat_messages` are created in TASK-063B1.

## Transaction Boundaries

Preparation keeps the database work short and stops before any future provider call. At the end of a successful preparation:

- the idempotency record is `processing`
- the session message slot has been consumed exactly once
- a stable widget conversation is attached
- no RAG/provider execution has occurred

Failures before processing ownership do not consume a slot. Failures after processing ownership mark the idempotency record failed. Failures after slot consumption keep the slot consumed unless a future implementation can safely guarantee rollback.

## Gateway Extension

`PublicAccessGateway` now has an internal `message_send` extension point. It remains route-less in TASK-063B1. A future public route must still run credential resolution, tenant resolution, request limits, Origin validation, and `widget_message_send` rate limiting before preparation.

## Safe Errors And Events

New safe error codes include `invalid_message`, `message_too_large`, `idempotency_key_required`, `invalid_idempotency_key`, `idempotency_conflict`, and `request_in_progress`.

Safe preparation events include validation rejection, idempotency duplicate/conflict/in-progress states, slot consumption, conversation creation/attachment, completion, and failure. Events do not include raw messages, raw idempotency keys, session tokens, public keys, Origin values, or hashes.

## Local Commands

```powershell
docker compose up -d postgres redis
cd apps/api
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
python -m pytest tests/test_public_message_preparation.py
```

The normal unit suite must not require Docker.

## TASK-063B2 Security Preparation Update

TASK-063B2 adds the internal abuse-screening and cost-protection layer that runs after TASK-063B1 preparation and before any future retrieval/RAG/provider execution.

The layer evaluates `PreparedPublicMessage`, applies deterministic abuse rules, resolves server-owned cost ceilings, checks the AI model registry, evaluates optional quota snapshots, and returns `SecuredPublicMessage`. Security rejection marks the idempotency record failed and leaves the already-consumed TASK-063B1 message slot intact. Duplicate retries with the same idempotency key therefore converge on the stable failed idempotency state and do not consume another slot.

No public message route, public HTTP schema, RAG adapter, retrieval call, provider execution, user/assistant message persistence, output sanitiser, streaming, widget SDK/UI, billing, or quota table was added.
