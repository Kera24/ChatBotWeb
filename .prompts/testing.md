# Prompt Template: Testing

Use this when the task is specifically about adding/fixing tests (not primarily a feature change).

## Scope

`apps/api/tests/*`, co-located `apps/web/**/*.test.tsx`, `apps/widget/test/*`, `packages/widget-sdk/test/*`, `tests/widget-browser/specs/*`. See `docs/architecture/testing.md` for the full decision table.

## Constraints

- Backend: no shared `conftest.py` exists — copy the nearest existing similar test file's `client` fixture boilerplate rather than introducing a shared fixture file.
- Frontend: co-locate `*.test.tsx` next to the component; mock the `lib/api/*` boundary, never make a real network call.
- Match the nearest existing test's assertion style and helper-function shape for the feature area you're testing.
- A new test must actually fail without your fix and pass with it — verify this, don't just add an assertion that happens to already be true.

## Validation

Run the specific new/changed test file first in isolation, then the relevant broader suite (`docs/validation-policy.md`) to confirm no regression.

## Reporting

Short Report: which test file(s), what they verify, pass/fail counts before and after.

## Expected output

New/extended test file(s) only, following the exact fixture/helper conventions already established in that area — no production code changes unless the task explicitly also asked for a fix.

## What NOT to modify

- Test infrastructure shared across many files (Vitest config, Playwright config) unless the task is specifically about that.
- Existing passing tests' assertions, to make a new test pass — if an existing test needs to change, that's a signal to understand why before proceeding, not to route around it.
