# TASK-062B - Public Widget Configuration Endpoint Implementation

Status: Complete
Type: Implementation
Sprint: Sprint 3C - Public Channels

## Objective

Implement the public read-only widget configuration endpoint:

```text
GET /api/v1/widget/{public_key}/config
OPTIONS /api/v1/widget/{public_key}/config
```

The endpoint returns only published, sanitised, public-safe widget configuration. It does not create sessions, conversations, messages, retrieval requests, RAG executions, or AI Core executions.

## Implemented Scope

- Extended the existing public widget router with route-scoped `GET` and `OPTIONS` config handlers.
- Added Public Access Gateway `config_read` operation support.
- Extended the widget channel adapter to validate config-read request shape.
- Added versioned public widget configuration response schemas.
- Added a dedicated projection/sanitisation boundary for public widget config.
- Added safe asset URL projection for HTTPS raster assets and configured base URL support.
- Added dynamic CORS headers based on validated Origin.
- Added safe ETag generation and `If-None-Match` conditional GET support.
- Added conservative `Cache-Control` and `Vary: Origin` headers.
- Added safe widget config operational events.
- Added endpoint tests covering success, eligibility, Origin/CORS, rate limiting, ETag/cache, dashboard header rejection, and asset safety.

## Non-Goals Preserved

TASK-062B does not implement:

- Public widget message endpoint.
- Session validation endpoint.
- RAG, retrieval, or AI Core calls.
- Conversation or message persistence.
- Widget SDK/UI.
- Asset upload or proxy streaming.
- Redis/CDN configuration cache.
- Lead capture or production analytics.
- Provider/model/prompt exposure.
- Arbitrary CSS/HTML/JavaScript.
- Global CORS wildcard.

## Verification

Focused verification completed:

- `python -m pytest tests/test_public_widget_configuration_endpoint.py`
- `python -m pytest tests/test_public_widget_session_endpoint.py`
- `python -m pytest tests/test_public_widget_configuration_endpoint.py tests/test_public_widget_session_endpoint.py tests/test_public_access_layer.py`
- `python -m pytest tests/test_origin_validation.py tests/test_rate_limit.py tests/test_public_sessions.py`
- `python -m compileall app`

Full requested verification remains to be run after documentation updates:

- `docker compose up -d postgres redis`
- `python -m alembic upgrade head` from `apps/api` with PostgreSQL `DATABASE_URL`
- `npm run api:install`
- `npm run api:test`
- `npm run web:test`
- `npm run verify`
- `git diff --check`
