# Prompt Template: Frontend UI

Use this when the task is adding/changing a page or component in `apps/web`.

## Scope

Next.js App Router pages/components under `apps/web/app/`, `apps/web/components/`, `apps/web/lib/api/`, `apps/web/lib/auth/`. See `docs/architecture/frontend.md` and `docs/design/design-system.md`.

## Constraints

- Server Component page → `requireDashboardSession()` → typed `lib/api/<feature>.ts` loader → dumb component. No client-side fetching for initial load.
- No new CSS framework, component library, or state-management library.
- Reuse existing CSS classes (`.card`, `.badge`, `.actionButton`, state-panel classes) before writing new CSS — check `docs/design/design-system.md` first.
- New top-level page → update both `lib/navigation.ts` and `dashboard-shell.tsx`'s `navIcons`.
- Do not redesign or restructure a page/component you weren't asked to touch.

## Validation

`npm run web:lint && npm run web:build && npm run web:test` (see `docs/validation-policy.md`). If the change is visually significant, actually run the dev server and look at it (see the `run` skill) before reporting done — do not claim a UI "works" from a type check alone.

## Reporting

Short Report by default (`docs/reporting-policy.md`): files changed, validation run, remaining limitations, git status.

## Expected output

New/modified `.tsx` files following the standard page pattern, a co-located `*.test.tsx` for new components, no unrelated files touched.

## What NOT to modify

- `globals.css`'s existing token/class definitions (only append new, narrowly-scoped classes if truly needed).
- Any page/component outside the feature you were asked to work on.
- `dashboard-shell.tsx`'s structure beyond the one-line nav-icon addition for a new page.
