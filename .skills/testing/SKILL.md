# Skill: Testing

## Purpose

Add or fix tests across the backend, frontend, widget, or SDK.

## When to use

Any task primarily about test coverage rather than feature behavior. Full reference: `docs/architecture/testing.md`.

## Architecture assumptions

- Backend: no shared `conftest.py` — every test file defines its own `client` fixture (in-memory SQLite, `Base.metadata.create_all`, dependency override). Auth via dev headers.
- Frontend: Vitest + Testing Library, co-located `*.test.tsx`, `lib/api/*` is the mock boundary.
- Widget/SDK: Vitest unit tests per package; `tests/widget-browser/` is Playwright for e2e, `workers: 1`/`fullyParallel: false` (sequential by design).

## Files typically modified

- `apps/api/tests/test_<feature>*.py`
- `apps/web/**/*.test.tsx` (co-located)
- `apps/widget/test/*.test.{ts,tsx}`, `packages/widget-sdk/test/*.test.ts`
- `tests/widget-browser/specs/*.spec.ts`

## Files never modified

- Shared test infrastructure (Vitest/Playwright config files) unless the task is specifically about that infrastructure.
- Production code, unless the task explicitly also asks for a fix alongside the test (state this explicitly in the report if so).

## Validation commands

Run the new/changed test file directly first, then the broader suite per `docs/validation-policy.md`'s decision table for the area touched.

## Expected report format

Short Report: which file(s), what's verified, pass/fail counts before and after the change.

## Common pitfalls

- Writing an assertion that's already true without your fix — always confirm a new test fails on the old code path first if it's meant to catch a regression.
- Backend: forgetting to restore mutated `settings` frozen-dataclass fields in a fixture's teardown (`object.__setattr__(settings, "X", original)`), leaking state into later tests in the same file.
- Frontend: making a real network call in a unit test because `lib/api/*` wasn't mocked.
- Introducing a shared `conftest.py` for backend tests — this codebase has deliberately chosen per-file fixtures; don't refactor toward a shared one as a side effect of adding a test.

## Best practices

- Copy the nearest existing test file in the same feature area for fixture/helper conventions rather than starting from a blank file.
- For a bug fix, write the failing test first, confirm it fails, then fix, then confirm it passes.
- When a migration changes the Alembic head revision, remember `apps/api/tests/test_alembic_compat.py` hardcodes the expected head string and needs updating.
