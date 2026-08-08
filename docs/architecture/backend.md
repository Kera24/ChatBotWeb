# Backend Architecture

`apps/api` — FastAPI, SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Postgres/pgvector in production, SQLite for local dev/tests. No async ORM usage (sync `Session` throughout).

## Directory shape

```
app/main.py               create_app(), middleware, router registration
app/core/config.py         Settings (frozen dataclass) - the only config source
app/api/deps.py            DbSession, RBAC dependencies, current-user resolution
app/api/v1/<feature>.py    one router file per feature, registered in app/api/v1/router.py
app/db/models/<name>.py    one SQLAlchemy model file per entity (or small group)
app/db/session.py          engine + SessionLocal + get_db()
app/repositories/<feature>_repository.py   plain functions, db: Session first arg
app/services/<name>.py     business logic that isn't naturally a repository
app/ai/                    RAG orchestrator, guardrails, providers - see retrieval.md, guardrails.md
app/access/                public widget access layer (gateway, channels, rate limiting, origin validation)
app/auth/, app/billing/, app/evaluation/, app/observability/   feature-specific service modules
app/schemas/<feature>.py   Pydantic response/request models
alembic/versions/          migrations, NNNN_description.py
```

## Request lifecycle

`request_context_middleware` (`app/main.py`) runs first: assigns `request.state.request_id` (from `X-Request-ID` header if valid, else generated) and `request.state.trace_id` (AI observability correlation id, see `observability.md`), echoes both as response headers. Then FastAPI's normal dependency injection resolves `DbSession` (`Depends(get_db)`) and the RBAC dependency before the route body runs.

## RBAC pattern

`app.api.deps.require_organisation_role(allowed_roles: set[str])` is a dependency factory. Module-scope convention:

```python
FeatureViewerDependency = Annotated[DevelopmentCurrentUser, Depends(require_organisation_role({"org_owner", "client_admin", "viewer"}))]
FeatureManagerDependency = Annotated[DevelopmentCurrentUser, Depends(require_organisation_role({"org_owner", "client_admin"}))]
```

Every tenant-scoped route takes `workspace_id` as a path param and `organisation_id` as a required query param ("temporary tenant context required until production auth can infer organisation access safely" — this is a known, deliberate, documented interim state, not an oversight). Every repository lookup filters by both; every detail-fetch verifies the returned row's tenant IDs match, 404 (not 403) on mismatch. See `authentication.md` for the full RBAC/session picture.

## Repository pattern

Plain functions, not classes, `db: Session` as the first parameter, one file per feature in `app/repositories/`. Reference: `app/repositories/conversation_repository.py`. Do not introduce a repository *class* pattern — it doesn't match the rest of the codebase.

## Response envelope

`app.schemas.common.success_response(data, meta={})` → `{"success": true, "data": ..., "meta": {...}}`. Every route returns this shape.

## Adding a new endpoint — checklist

1. Repository function(s) in `app/repositories/<feature>_repository.py` (or extend existing).
2. Pydantic schema(s) in `app/schemas/<feature>.py`.
3. Route in `app/api/v1/<feature>.py` (new file, or extend existing), with an RBAC dependency matching the nearest precedent for the sensitivity of the data.
4. Register the router in `app/api/v1/router.py`'s `API_V1_ROUTER_REGISTRATIONS` tuple (new feature) — existing features are already registered.
5. Test file in `apps/api/tests/test_<feature>_api.py` following the nearest existing fixture pattern (see `testing.md`).

## What NOT to do

- Do not add an async route unless the whole call chain below it is already async (it isn't, today).
- Do not introduce a second ORM/query-building pattern.
- Do not skip the tenant-match verification on a detail-fetch endpoint.
- Do not put business logic directly in a route handler if a repository/service function is the established location for it elsewhere in the same feature area.
