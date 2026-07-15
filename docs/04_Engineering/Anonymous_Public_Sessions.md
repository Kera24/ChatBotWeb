# Anonymous Public Sessions

Status: Implemented internal foundation. No public session, config, message, or RAG endpoint exists.

## Module Layout

TASK-060B adds `apps/api/app/access/sessions`:

- `contracts.py` defines creation, validation, validated-context, message-slot, and operation-result contracts.
- `tokens.py` generates, parses, hashes, and verifies opaque public session tokens.
- `repository.py` provides tenant-safe persistence, lifecycle, message-count, conversation-attachment, and lazy-expiry helpers.
- `service.py` enforces token verification, lifecycle, credential/tenant/channel/environment/policy/origin binding, expiry extension, message caps, and safe events.
- `dependencies.py` contains an explicit factory helper.

## Schema

`public_sessions` stores one durable anonymous public-session record per created session:

- tenant binding: `organisation_id`, `workspace_id`, `credential_id`
- channel binding: `channel`, `environment`, `policy_profile`
- token lookup/proof: `public_token_id`, `token_secret_hash`, `token_hash_version`
- lifecycle: `status`, `created_at`, `updated_at`, `last_activity_at`, `expires_at`, `absolute_expires_at`, terminal timestamps, `deleted_at`
- optional binding: `origin_id`, `canonical_origin_hash`, `conversation_id`, `anonymous_user_id`
- limits and safe metadata: `message_count`, `metadata_json`

Indexes cover token lookup, tenant/workspace, tenant/credential, credential/status, status/expiry, last activity, conversation, and deleted filtering. The migration seeds no sessions and leaves all existing workspaces private.

## Token Format And Hashing

Tokens are opaque bearer material:

```text
pss_dev_<token_id>.<secret>
pss_stg_<token_id>.<secret>
pss_live_<token_id>.<secret>
```

The token ID and secret are generated independently with standard-library cryptographic randomness. Tokens are URL-safe, non-sequential, bounded in length, and contain no tenant, workspace, credential, origin, or conversation data.

Only `public_token_id` and a keyed HMAC secret hash are stored. The full token and secret are returned only once at creation and must not be logged or included in events. Verification uses deterministic HMAC plus constant-time comparison. The stored `token_hash_version` is the key-rotation extension point.

## Lifecycle And Expiry

Supported statuses:

- `active`
- `completed`
- `expired`
- `revoked`
- `blocked`

Terminal statuses do not return to active. Validation enforces inactivity expiry through `expires_at` and absolute expiry through `absolute_expires_at`. Valid activity extends `expires_at`, capped by `absolute_expires_at`. Lazy expiry marks expired rows during validation or batch helpers.

## Binding Rules

Validation checks all of the following before returning a usable internal context:

- token format and environment prefix
- token ID lookup and constant-time secret verification
- active session status and expiry
- organisation/workspace binding and active checks
- credential ID binding and active credential recheck
- credential environment and channel compatibility
- policy-profile binding
- canonical origin hash when the policy requires origin binding
- message cap

Cross-tenant replay and invalid-secret cases map to safe invalid-session style errors where practical.

## Message Slots

`consume_message_slot` increments `message_count` with an atomic conditional database update. It only runs after successful validation and cannot exceed the policy/session message cap. The MVP decision is that a consumed slot is not refunded for downstream provider/RAG failure, because the slot is consumed immediately before future expensive processing to reduce replay and abuse complexity.

TASK-060B does not call RAG.

## Conversation Attachment

`conversation_id` starts as null. `attach_conversation` accepts only a trusted internal conversation ID, verifies tenant/workspace ownership when attaching, and uses compare-and-set semantics. If a conversation is already attached, the existing ID is returned. Public clients must not submit trusted conversation IDs.

## Gateway Integration

`PublicAccessGateway` accepts an optional injected `PublicSessionService`. The session stage is inert unless `session_operation` is explicit:

- `session_creation`: runs after request validation, credential/tenant/policy resolution, origin validation, and rate limiting; creates a session and stops before RAG.
- `session_validation`: requires a token, validates the session after origin and rate limiting, optionally consumes a message slot, returns a validated internal access context, and stops before RAG.

No route is added by TASK-060B.

## Safe Errors And Events

Session errors include `invalid_session`, `expired_session`, `revoked_session`, `blocked_session`, `completed_session`, `session_limit_reached`, `session_origin_mismatch`, `session_credential_mismatch`, and `session_channel_mismatch`. They do not expose internal session IDs, tenant IDs, token IDs, token hashes, secrets, configured origins, or policy internals.

Operational events include `public_session.created`, `public_session.validated`, `public_session.expired`, `public_session.rejected`, `public_session.revoked`, `public_session.blocked`, `public_session.completed`, `public_session.origin_mismatch`, `public_session.message_limit_reached`, `public_session.conversation_attached`, and `public_session.credential_invalidated`. Events must not include full tokens, secrets, token hashes, or raw origins.

## Cleanup Extension Points

Current helpers support lazy batch expiry. Future tasks may add scheduler wiring and retention operations for archive/delete, revoke by credential, revoke by workspace, and revoke by organisation. Those background jobs are intentionally not implemented here.

## Local Commands

```bash
cd apps/api
python -m pytest tests/test_public_sessions.py
python -m pytest tests/test_public_access_layer.py tests/test_origin_validation.py tests/test_rate_limit.py tests/test_public_sessions.py
```

PostgreSQL migration verification:

```bash
docker compose up -d postgres redis
cd apps/api
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
```

Repository-level verification remains:

```bash
npm run api:install
npm run api:test
npm run verify
git diff --check
```

## Public Endpoint Warning

TASK-060B exposes no public session endpoint, public widget configuration endpoint, public message endpoint, widget SDK/UI, CORS middleware, Redis session cache, conversation creation from public requests, or RAG invocation. Browser storage guidance remains a future widget concern; the architecture preference is iframe `sessionStorage` with stricter in-memory mode where needed.