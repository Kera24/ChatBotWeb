# TASK-060B: Anonymous Public Session Implementation

Status: Implemented
Type: Implementation task
Sprint: Sprint 3B - Public Access Foundation

## Linked Architecture

- `planning/tasks/TASK-060A-anonymous-public-session-architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `docs/adr/0010-anonymous-public-session-security.md`

## Objective

Implement the persistent anonymous public-session foundation, secure opaque token generation and verification, session lifecycle management, credential/origin/channel binding, and optional Public Access Gateway session-stage integration.

No public session endpoint, public widget configuration endpoint, public message endpoint, widget SDK/UI, Redis session cache, CORS middleware, conversation creation from public requests, cleanup scheduler, or RAG invocation is implemented by this task.

## Implemented Scope

- SQLAlchemy `public_sessions` model and Alembic migration.
- Opaque token format: `pss_<environment>_<token_id>.<secret>`.
- Keyed HMAC token secret hashing with version storage and constant-time verification.
- Privacy-safe canonical-origin HMAC binding.
- Session creation, validation, message-slot consumption, terminal lifecycle transitions, lazy expiry, and lazy conversation attachment services.
- Tenant-safe repository methods; runtime token-ID lookup is only the first verification step.
- Optional Public Access Gateway session stage with explicit `session_creation` and `session_validation` modes.
- Safe public errors and operational events.
- Focused unit tests for tokens, model/migration, repository, service behavior, gateway ordering, and safe no-route behavior.
- Engineering documentation at `docs/04_Engineering/Anonymous_Public_Sessions.md`.

## Explicitly Not Implemented

- Public session endpoint.
- Public config endpoint.
- Public message endpoint.
- RAG invocation.
- Widget SDK/UI.
- Redis session cache.
- CORS middleware.
- Lead capture.
- Conversation creation from public requests.
- Cleanup scheduler.
- Domain ownership verification.
- Production analytics.
- Browser storage code.

## Verification

Focused commands:

```bash
cd apps/api
python -m pytest tests/test_public_sessions.py
python -m pytest tests/test_public_access_layer.py tests/test_origin_validation.py tests/test_rate_limit.py tests/test_public_sessions.py
```

Required repository commands:

```bash
docker compose up -d postgres redis
cd apps/api
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb"
python -m alembic upgrade head
cd ../..
npm run api:install
npm run api:test
npm run verify
git diff --check
```

## Acceptance Criteria

- [x] Model and migration exist.
- [x] Token format and keyed hashing are implemented without raw token storage.
- [x] Repository methods are tenant-safe except first-step token-ID verification lookup.
- [x] Service enforces lifecycle, expiry, credential, tenant, channel, environment, policy, origin, and message-cap checks.
- [x] Message-slot consumption is atomic and capped.
- [x] Lazy conversation attachment is compare-and-set style and tenant-safe.
- [x] Gateway session stage is optional, explicit, and stops before RAG.
- [x] Safe errors and events exclude tokens, secrets, hashes, raw origins, and tenant details.
- [x] Tests cover token, repository/model, service, and gateway behavior.
- [x] No public endpoint is added.