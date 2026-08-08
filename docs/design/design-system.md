# Conversa Design System

The permanent UI reference for `apps/web`. Read this before writing any new CSS or component — reuse an existing class/pattern before inventing one. For the design *philosophy* behind these choices ("controlled Expressionism"), see `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`.

**Supersedes `docs/05_Design/01_Design_System.md` as the accurate current-state reference.** That earlier document (Version 0.1, Status: Draft) describes an early "light SaaS interface, blue primary actions" direction that predates and differs from what was actually implemented (a dark-navy `--brand-primary` per the Manifesto's later "controlled Expressionism" direction). Keep the older document for historical intent; treat this file as the source of truth for the actual current tokens/classes.

## Methodology

Plain CSS, no framework. Single file: `apps/web/app/globals.css` (~13,300 lines). No Tailwind, no Radix/shadcn/MUI, no CSS-in-JS, no CSS Modules. No shared `components/ui/` primitives folder — reuse happens through **shared class names** used across many feature-specific components (`.card`, `.badge`, `.actionButton`), not exported React components. Only two runtime UI dependencies: `framer-motion` (animation) and `lucide-react` (icons).

Before adding new CSS: search `globals.css` for an existing class that already does what you need. This file has been extended incrementally by many features — duplication is the actual failure mode to watch for, not a lack of expressiveness.

## Typography

- Font stack: `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- No fixed type scale is centrally defined as tokens (no `--font-size-sm/md/lg` variables) — heading/body sizes are set per-component-class. Match the nearest existing similar component's heading/body size rather than picking an arbitrary value.

## Color system / semantic tokens

Tokens are layered in `globals.css` (search for the exact `:root` block before using a name, as multiple layers exist — later layers generally take precedence for newer components):

- **Brand**: `--brand-primary: #1b2a4a` (+ `-950/-900/-800/-700/-600/-100/-50` shade variants), `--brand-accent`, `--brand-info`, `--brand-warning`.
- **Surfaces**: `--surface`, `--surface-strong`, `--surface-muted`, `--surface-elevated`.
- **Text**: `--ink`, `--muted`, `--text-primary`, `--text-secondary`, `--text-muted`, `--foreground`.
- **Structure**: `--line`, `--border`, `--border-strong`.
- **Status**: `--success`, `--warning`, `--danger`, `--information`.
- **Interaction**: `--focus`, `--focus-ring`.
- **Elevation**: `--shadow`, `--shadow-soft`.

Status-badge coloring convention (used across conversations/citations/answer-state/guardrail/stage UI — see `docs/03_AI/AI_Metrics_Dictionary.md` for the AI-specific instance): green family for success/passed/answered states, amber/orange for fallback/low-confidence/warning states, red for failed/blocked/error states, grey/muted for skipped/unknown/neutral states. New status badges should follow this mapping rather than inventing new colors.

## Spacing

No centralized spacing scale token (no `--space-1/2/3` variables) — spacing is set per-component in pixels, commonly in multiples of 4px (4/8/12/16/18/22/24px are the most frequent values seen across the file). Match the spacing rhythm of the nearest similar component rather than introducing a new increment.

## Cards, badges, buttons, panels (shared class groups)

- `.card`, `.statePanel`, `.overviewPanel` (and several feature-specific aliases) share one base rule: `background: var(--surface-strong)`, `border: 1px solid var(--line)`, `border-radius: 8px`, `box-shadow: var(--shadow-soft)`.
- `.badge`, `.conversationStatusBadge`, `.reviewStatusBadge`, `.widgetStatusBadge` share pill styling: `border-radius: 999px`, `border: 1px solid rgba(27,42,74,0.14)`, `background: var(--brand-primary-50)`, `color: var(--brand-primary)`. Status-specific variants (`.answerState-answered`, `.stageStatus-ok`, etc. — see the observability UI for a recent example) override background/color per the status-color convention above.
- `.actionButton`, `.smallButton`, `button[type="submit"]` share primary-button styling: bordered, `var(--brand-primary)` background, white text, soft shadow, `transform`/`box-shadow`/`background`/`opacity` transitions on hover.

## Forms

No shared form-input component class family is centralized — form fields are typically styled inline within their feature's component (see the observability dashboard's filter form, `apps/web/components/observability/observability-dashboard.tsx`, for a recent minimal example: bordered `<select>`/`<input>` with `var(--line)` border, `var(--surface-elevated)` background). Match the nearest existing form in the same feature area rather than a distant one.

## Tables

No dedicated table component/class family — most list data uses card-list patterns instead (see "Cards" above and `ConversationInbox`/`observabilityTraceList` for reference row-list layouts: a flex/grid row per item, hover elevation, status badge, metadata spans). Prefer a card-list over an HTML `<table>` unless the data is genuinely tabular (many columns, needs column alignment) — this matches the rest of the product.

## Dialogs

No shared modal/dialog primitive was found in the researched areas — check the specific feature you're working in (e.g. widget publish flow, role-assignment dialog in `components/users/role-dialog.tsx`) for the nearest precedent before building a new one.

## Charts

Use the `dataviz` skill (see the skills list available to Claude Code) for chart color/form guidance whenever adding a chart, graph, or stat tile — it defines a validated, accessible palette and mark-spec method independent of this design system's own tokens. Do not hand-pick chart colors from the brand palette without going through that skill first.

## Animation and motion

`framer-motion` is the only animation library. Convention seen throughout (e.g. `analytics-dashboard.tsx`, `conversations-view.tsx`): page-level fade+slide-up on mount (`initial: {opacity:0, y:16}`, `animate: {opacity:1, y:0}`, `duration: 0.32`, `ease: [0.22,1,0.36,1]`), always gated behind `useReducedMotion()` (falls back to `initial: false, animate: {}}` when the user prefers reduced motion — **never skip this gate on a new animated component**). Secondary content fades in with a short delay (`duration: 0.25, delay: 0.05`) after the page-level animation.

## Accessibility

- `useReducedMotion()` gate on every animated component (see above) — mandatory, not optional, per the Manifesto's "Accessibility and contrast remain mandatory" constraint.
- Status must never be color-only — pair every status badge with a text label (see the widget's own accessibility test suite, `accessibility-release.spec.ts`, which explicitly asserts fallback/low-confidence states use a "visible non-colour-only label").
- `aria-live`/`aria-busy` used on loading states (see `LoadingState` in `components/conversations/state-panels.tsx`).
- Keyboard focus: interactive elements get a visible `--focus-ring` outline on `:focus-visible`.

## Responsive breakpoints

No fixed named breakpoint scale — `max-width` media queries are added per-component at whatever width the component actually needs adjustment, commonly at `480/560/640/720/760/840/860/900/920/1000/1080/1180px`. When adding responsive behavior, pick the breakpoint where *your* component actually breaks, don't force it into an unrelated existing breakpoint.

## Loading / empty / error / success states

- **Loading**: `LoadingState` (`components/conversations/state-panels.tsx`) — reusable across features despite the folder name; a `.statePanel` with `aria-live="polite" aria-busy="true"`, a kicker label, heading, and description. Feature-specific skeleton block classes also exist (`.analyticsSkeletonBlock`, `.overviewSkeletonBlock`) with a shimmer animation.
- **Empty**: pattern is a `<section className="conversationEmptyHero">`-style hero (icon + heading + description + one or two CTA links) — see `components/conversations/conversation-empty-states.tsx` for `NoAssistantSelectedState`/`NoConversationsState`/`NoFilterResultsState` as the reference shape to copy for a new feature's empty states.
- **Error**: `ErrorState` (same file) — a `.statePanel.urgentState` with the failure message and a "Retry" `.actionButton` link back to the current route.
- **Access denied**: `AccessDeniedState` — same shape, fixed copy, no retry link (retrying won't fix a permissions problem).
- **Success**: no single shared "success state" component — success is typically communicated via the badge/status system (see Color system) plus the page simply rendering its normal populated content; use a toast/inline confirmation only if the nearest precedent for that specific interaction already has one.

## Assistant cards / analytics cards

No single generic "MetricCard"/"AssistantCard" component is exported — each feature defines its own small card component matching the shared `.card`/`.metricTile` styling (see `.metricTile` — a large-number stat tile with a dark gradient background, used for headline metrics; and each feature's own `*MetricCard`/`*-metric-card` component for smaller stat groupings, e.g. `apps/web/components/observability/observability-dashboard.tsx`'s `MetricCard`). When adding a new metrics dashboard, copy the shape of the nearest existing one (Analytics or Observability) rather than the generic `.metricTile`.

## Dashboard layouts

Every authenticated page renders inside `DashboardShell` (`components/dashboard-shell.tsx`): sidebar (brand, workspace card, nav from `lib/navigation.ts`, security-status footer) + topbar (breadcrumbs, command palette, assistant switcher, notifications, user menu) + `quickActions` row + the page's own content, animated in via `framer-motion` on route change. `/` and `/pricing` render standalone without this shell. See `docs/architecture/frontend.md` for the page-composition pattern that fills the content area.

## Navigation

Single source of truth: `apps/web/lib/navigation.ts`'s `navigationItems` array (label/href/glyph/description/group). Icons are mapped separately in `dashboard-shell.tsx`'s `navIcons` record (lucide-react icon per href) — **both must be updated together** when adding a new top-level page. Active-item highlighting matches exact path or path-prefix.

## Icons

`lucide-react` exclusively. No custom SVG icon set. Pick the closest semantically-named Lucide icon rather than introducing a new icon library or hand-drawn SVG.

## Dark mode / light mode

- Driven by `@media (prefers-color-scheme: dark)` (OS-level), **not** a JS-toggled `.dark` class or `data-theme` attribute — no such toggle mechanism exists in the codebase today.
- A later "final readability layer" in `globals.css` deliberately **overrides** the OS dark preference for many surfaces (forces light backgrounds/dark text) to keep cards/panels legible — verified by `apps/web/app/theme-contrast.test.ts`, which asserts on `globals.css` content directly. This means the product does not currently render a true full dark theme even on a dark-preferring OS; it renders a light-leaning "readability-safe" theme with some dark accents.
- Numerous `.dark <selector>` CSS rules exist scattered through the file but are currently **dormant** (nothing ever applies a `dark` class). Do not assume they're live; if asked to build a real dark-mode toggle, that's new work (see `docs/architecture/future-roadmap.md`), not a matter of "just adding a toggle" — verify current OS-driven behavior first with `theme-contrast.test.ts` as your regression guard.

## Micro-interactions

- Hover: cards/rows lift slightly (`transform: translateY(-1px to -2px)`) with an increased shadow and a brand-colored border, transition ~150-160ms ease.
- Buttons: `transform`/`box-shadow`/`background`/`opacity` transitions on hover/active, ~150ms ease.
- Page transitions: see Animation and motion above.

## Adding a new UI surface — checklist

1. Search `globals.css` for an existing class that already matches what you need before writing new CSS.
2. Match the nearest existing similar feature's component composition (loader → page → dumb component, see `docs/architecture/frontend.md`).
3. Use the shared `.card`/`.badge`/`.actionButton`/state-panel classes rather than new ad hoc styling.
4. Gate any animation behind `useReducedMotion()`.
5. Pair every status color with a text label.
6. If it's a chart/stat visualization, load the `dataviz` skill first.
7. If it's a new top-level page, update both `lib/navigation.ts` and `dashboard-shell.tsx`'s `navIcons`.
