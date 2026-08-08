# Frontend Architecture

`apps/web` — Next.js App Router, TypeScript, plain CSS (see `docs/design/design-system.md`). No Redux/Zustand/React Query — Server Components fetch data server-side per request.

## The standard page pattern

Every dashboard page follows this shape (reference: `apps/web/app/analytics/page.tsx`, `apps/web/app/conversations/page.tsx`):

1. `app/<route>/page.tsx` — a Server Component (`export const dynamic = "force-dynamic"`), `async function Page({ searchParams })`.
2. Calls `requireDashboardSession()` (`lib/auth/session.ts`) — redirects to `/login` or `/onboarding` if session/onboarding state doesn't allow the page.
3. Calls one or more typed loaders from `lib/api/<feature>.ts`, wrapped in a local `try/catch` that maps to `{ok: true, data}` / `{ok: false, error: DashboardApiError}`.
4. On `!ok`, renders `AccessDeniedState` (for `error.kind === "forbidden"`) or `ErrorState` (otherwise), both from `components/conversations/state-panels.tsx` (shared across features despite the "conversations" folder name).
5. On success, renders a dumb presentational component from `components/<feature>/`.

## API client layer (`lib/api/`)

- `lib/api/client.ts` — `dashboardApiGet/Post/Patch/Delete/PostForm`, all funnel through `dashboardApiRequest`: builds the URL from `getDashboardApiBaseUrl()` (`NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`), forwards the browser's session cookie server-side via `next/headers`, throws `DashboardApiError` on non-2xx.
- `lib/api/errors.ts` — `DashboardApiError` (`kind`: `unauthorized`/`forbidden`/`not_found`/`conflict`/`validation`/`network`/`server`/`unknown`), `messageForApiError()` for user-facing text.
- `lib/api/types.ts` — `ApiEnvelope<TData, TMeta>` matching the backend's `success_response()` shape.
- One file per feature (`lib/api/conversations.ts`, `lib/api/analytics.ts`, `lib/api/billing.ts`, `lib/api/observability.ts`, ...), each exporting typed functions that call `dashboardApiGet`/etc. with the feature's actual route paths.

## Auth/session (`lib/auth/`)

- `lib/auth/session.ts::requireDashboardSession()` — the gate every protected page calls first.
- `lib/auth/development-session.ts` — `DashboardSession`/`DashboardRole` types, `dashboardSessionFromAuthContext()` converts the API's `/auth/me` response into the session shape components use (`organisationId`, `workspaceId`, `role`, etc). Despite the filename, this is used in all environments, not just development — see `authentication.md` for why.

## Component organization

`components/<feature>/` — one folder per feature, e.g. `components/billing/`, `components/conversations/`, `components/observability/`. Inside: presentational components (often one large "view"/"dashboard" component composed of smaller pieces), usually co-located `*.test.tsx` files. No shared `components/ui/` primitives folder exists — buttons/cards/badges are shared via CSS class name convention (`.actionButton`, `.card`, `.badge`), not exported React components. See `docs/design/design-system.md`.

## Navigation and shell

- `lib/navigation.ts` — the single source of truth `navigationItems` array (label, href, glyph, description, group).
- `components/dashboard-shell.tsx` — renders the sidebar/topbar chrome for every route except `/` and `/pricing` (which render standalone). Maps `navigationItems` to icons via a local `navIcons` record keyed by href — **add both** when adding a new top-level nav entry.

## Adding a new page — checklist

1. `lib/api/<feature>.ts` — typed loader(s), following the shape of an existing similar feature.
2. `app/<feature>/page.tsx` — Server Component following the standard pattern above.
3. `components/<feature>/<feature>-view.tsx` (or similar) — presentational component.
4. If it's a new top-level nav destination: one entry in `lib/navigation.ts` + one icon mapping in `dashboard-shell.tsx`'s `navIcons`. Do not restructure existing nav groups.
5. Co-located `*.test.tsx` for new components (Vitest + Testing Library — see `testing.md`).

## What NOT to do

- Do not add a client-side data-fetching library or global state manager.
- Do not add Tailwind or a component library.
- Do not fetch data directly inside a client component for initial page load — that belongs in the Server Component.
- Do not bypass `dashboardApiGet`/etc. with a raw `fetch()` call.
