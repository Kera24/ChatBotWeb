# Testing Conventions

See `docs/validation-policy.md` for *when* to run which command. This document describes *how tests are written* in each part of the repo.

## Backend (`apps/api/tests/`)

- Runner: `pytest` (`python -m pytest`, root script `npm run api:test`).
- **No shared `conftest.py`.** Every test file defines its own `client` fixture: an in-memory SQLite engine (`sqlite+pysqlite:///:memory:`, `StaticPool`, `check_same_thread=False`), `Base.metadata.create_all(engine)` (schema comes directly from the SQLAlchemy models, **not** from running Alembic migrations), `app.dependency_overrides[get_db]` pointed at that engine, wrapped in `fastapi.testclient.TestClient`.
- Auth in tests: dev headers (`X-Development-User-Email`, `X-Development-Role`) — works because `get_development_current_user` falls back to headers when `APP_ENV` is `development`/`test`/`testing` and no session cookie is present (see `authentication.md`).
- Seed helpers (`seed_tenant`, `add_embedded_chunk`, etc.) typically insert directly via the ORM inside a `with client.app.state.testing_session() as db:` block (the fixture stashes the test sessionmaker on `app.state.testing_session` for this purpose) rather than only through the API, for setup speed.
- New test files should copy the nearest existing similar file's fixture boilerplate rather than inventing a new pattern — this is deliberate, not an oversight (the codebase has judged per-file fixtures worth the duplication over a shared `conftest.py`).
- Migrations are validated separately from the main suite — see `apps/api/tests/test_alembic_compat.py`, which actually runs `alembic upgrade head`/`downgrade` against a throwaway file-based SQLite DB.

## Frontend (`apps/web`)

- Runner: Vitest (`vitest.config.ts`, `environment: "jsdom"`), `npm run web:test` → `vitest run`.
- Test files are **co-located** with source (`component.tsx` next to `component.test.tsx`), not in a separate `__tests__/` directory.
- `test/setup.ts` — jest-dom matchers, `IntersectionObserver` stub, auto-cleanup/restore-mocks after each test.
- Mocking boundary: `lib/api/*` modules are mocked with `vi.mock(...)` and stubbed per-test with `vi.mocked(fn).mockResolvedValue(...)` — unit tests never make real network calls.
- `globals: false` in Vitest config — always explicitly import `describe`/`it`/`expect` from `vitest`.

## Widget (`apps/widget`, `packages/widget-sdk`)

- Both have their own Vitest-based unit test suites (`apps/widget/test/*.test.{ts,tsx}`, `packages/widget-sdk/test/*.test.ts`). `widget-sdk`'s `test` script **builds the package first, then runs Vitest against the built output** — not pure source tests.
- End-to-end: `tests/widget-browser/` — Playwright (`playwright.config.ts`), `testDir: "./specs"`, projects for chromium/firefox/webkit plus a dedicated `visual-chromium` project for `visual-regression.spec.ts` (fixed viewport, light scheme, reduced motion). `fullyParallel: false`, `workers: 1` — the suite is written assuming sequential execution.

## Evaluation (`apps/api/app/evaluation`)

Not unit tests in the traditional sense — see `evaluation.md`. `npm run eval:test` runs a specific subset of `apps/api/tests/test_evaluation_*.py` files plus related fixtures/CLI/vector-search tests; it's a subset of the full `api:test` run, kept as a separate script because it's the most relevant slice when iterating on retrieval/evaluation specifically.

## Writing a new test — decision guide

| You changed | Add/extend |
|---|---|
| A backend route/repository/service | `apps/api/tests/test_<feature>_api.py` (or the nearest existing file for that feature) |
| `RAGOrchestrator` or a guardrail | `apps/api/tests/test_rag_orchestrator.py` + relevant guardrail-specific test file |
| A migration | `apps/api/tests/test_alembic_compat.py` if the head revision changed (update the hardcoded expected head string), plus normal model tests (schema comes from `Base.metadata`, not the migration, for those) |
| A frontend component | co-located `*.test.tsx`, mock the `lib/api/*` boundary |
| The widget iframe app or SDK | the relevant package's own `test/*.test.ts` |
| Widget embed behavior visible to the customer's page | a new/updated Playwright spec in `tests/widget-browser/specs/` |
