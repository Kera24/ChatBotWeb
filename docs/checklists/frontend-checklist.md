# Frontend Checklist

## Required validation

- `npm run web:lint && npm run web:build && npm run web:test` (`docs/validation-policy.md`).
- Dev server actually run and the feature clicked through in a browser — type checks aren't a substitute for looking at the UI (`CLAUDE.md`'s UI principles).

## Things to verify

- Server Component page (`app/<route>/page.tsx`) calls `requireDashboardSession()` then a typed loader in `lib/api/*.ts` — no client-side data fetching for initial page load.
- Presentational component stays dumb (props in, JSX out) — logic lives in the loader.
- Error handling uses `DashboardApiError`/`isDashboardApiError`/`messageForApiError` and `AccessDeniedState`/`ErrorState`, not a bespoke error UI.
- New CSS reuses `.card`/`.statePanel`/`.badge`/`.actionButton` and existing design tokens (`docs/design/design-system.md`) before adding new classes.
- New top-level page has exactly one nav entry (`lib/navigation.ts` + `dashboard-shell.tsx`'s `navIcons`) — no nav restructuring for a feature task.
- Co-located `*.test.tsx` mocks the `lib/api/*` boundary — no real network calls in a unit test.

## Common mistakes

- Fetching data client-side for the initial page load instead of through the Server Component loader.
- Introducing Tailwind, a component library, or a new CSS methodology.
- Restructuring the nav instead of adding one entry.
- Skipping the actual browser check and reporting "done" off a passing type check alone.

## Required documentation

- Update `docs/architecture/frontend.md` if the page/loader/component pattern itself changes.
- No new top-level docs directory — additions go in the existing structure.

## Definition of Done

Lint, build, and test all pass; the feature was seen working in a running browser (golden path + edge cases); no unrelated nav/CSS-framework changes; error states use existing components.
