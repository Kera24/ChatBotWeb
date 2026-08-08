# Skill: Frontend UI

## Purpose

Implement or modify a page/component in the Conversa dashboard (`apps/web`).

## When to use

Any task that adds a new dashboard page, modifies an existing page's UI, or adds/changes a presentational component. Not for widget (`apps/widget`)/SDK (`packages/widget-sdk`) work — see the `frontend-ui` skill's scope is the *dashboard*, not the embeddable widget.

## Architecture assumptions

- Next.js App Router, Server Components fetch data, no client-side data-fetching library. See `docs/architecture/frontend.md` in full.
- Plain CSS, no framework, no component library. See `docs/design/design-system.md`.
- Every protected page starts with `requireDashboardSession()`.
- `framer-motion` for animation (always gated behind `useReducedMotion()`), `lucide-react` for icons.

## Files typically modified

- `apps/web/app/<feature>/page.tsx` (new or existing).
- `apps/web/lib/api/<feature>.ts` (typed loader).
- `apps/web/components/<feature>/*.tsx` (presentational components) + co-located `*.test.tsx`.
- `apps/web/lib/navigation.ts` + `apps/web/components/dashboard-shell.tsx` (only if adding a new top-level nav destination).
- `apps/web/app/globals.css` (only to append new, narrowly-scoped classes after confirming nothing existing already covers the need).

## Files never modified

- `apps/api/**` (unless the task explicitly spans both — then treat it as two tasks, use `backend-api` skill for the API half).
- Other features' pages/components.
- `globals.css`'s existing token/class definitions.

## Validation commands

```
npm run web:lint
npm run web:build
npm run web:test
```
Then, for a visually significant change, run the dev server and actually look at the result (see the `run` skill) before reporting done.

## Expected report format

Short Report (`docs/reporting-policy.md`): files changed, validation commands run + results, remaining limitations (e.g. "not live-verified in a browser — environment constraint"), git status.

## Common pitfalls

- Fetching data in a client component instead of the Server Component page — breaks the established pattern and often duplicates a network round trip.
- Forgetting the `useReducedMotion()` gate on a new animated component.
- Writing new CSS for something `.card`/`.badge`/`.actionButton` already covers.
- Adding a nav entry to `lib/navigation.ts` without also adding the icon mapping in `dashboard-shell.tsx` (or vice versa) — the page becomes reachable but visually broken in the sidebar.
- Claiming a UI "works" from `web:build` passing alone — a build passing means it compiles, not that it renders correctly or matches the design.

## Best practices

- Find the nearest existing similar page (e.g. building a new dashboard? look at Analytics or Observability; building a new list+detail view? look at Conversations or Evaluation) and copy its composition shape exactly.
- Read `docs/design/design-system.md` before writing any new className.
- Keep the Server Component page thin — data loading and error-state branching only; put all rendering logic in the presentational component.
