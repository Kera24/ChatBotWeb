# Widget Rendering Foundation and Design Tokens

TASK-065B1 adds the first visual rendering foundation for the iframe widget app.

## Rendering Boundary

The iframe application now uses Preact for visual rendering. Preact is installed only in `apps/widget`; the loader SDK package remains framework-free.

The rendering layer consumes immutable snapshots from the existing framework-free `WidgetStateStore`. Public API services, session storage, config loading, message sending, and handshake logic remain outside presentational components.

Components must not receive or render public session tokens. Components do not call `fetch`, access `sessionStorage`, or communicate directly with the host page.

## Component Structure

Implemented structural components:

- `WidgetApp`
- `WidgetRoot`
- `WidgetLauncher`
- `WidgetPanel`
- `WidgetHeader`
- `WidgetStatusRegion`
- `WidgetViewport`
- `WidgetFooterShell`
- `WidgetLoadingState`
- `WidgetUnavailableState`

The shell deliberately does not implement welcome content, suggested questions, message thread, composer controls, citations, or privacy/terms content yet.

## Design Tokens

Tokens are typed and projected as CSS custom properties on the iframe root.

Groups include:

- colours
- typography
- spacing
- radii
- elevation
- motion
- dimensions
- focus

The CSS uses token variables rather than scattered raw values where practical.

## Branding Mapping

The public configuration contributes:

- `primary_colour`
- `secondary_colour`
- `theme_mode`
- `bot_name`
- `launcher_label`
- `position`
- future-safe logo/avatar inputs

Colours are revalidated client-side. Invalid colour input falls back to the platform accent. Semantic warning, danger, fallback, low-confidence, and focus colours remain platform-owned.

## Contrast Utilities

Implemented deterministic utilities for:

- supported hex parsing
- relative luminance
- contrast ratio
- readable foreground selection
- muted accent derivation
- hover/pressed accent derivation

Targets remain WCAG AA: 4.5:1 for normal text, 3:1 for large text and UI boundaries where applicable.

## Theme Modes

Supported:

- light
- dark
- auto/system

Auto mode listens to `prefers-color-scheme` and cleans up listeners on unmount/destroy. Explicit configuration takes precedence.

## Shell UX

The launcher is an accessible button with a local SVG placeholder mark, configured/fallback label, hover/focus/pressed states, and left/right positioning from validated config.

The open panel includes a header, safe avatar placeholder, bot name, non-deceptive `AI assistant` descriptor, close control, status region, semantic conversation viewport, and neutral footer shell.

No fake messages or inactive composer controls are rendered.

## Accessibility Foundation

Implemented foundation:

- iframe document language from config/locale with fallback
- launcher accessible label
- panel `dialog` semantics and heading
- close button label
- loading `role=status`
- unavailable `role=alert`
- focus-visible styles
- forced-colours support
- reduced-motion support
- 44px touch targets
- zoom/reflow-safe structural layout

The final focus trap, composer focus model, live message announcements, and full keyboard flows are deferred to later UI tasks.

## Resize Integration

Open/close states continue to use the existing SDK/iframe postMessage lifecycle. The iframe shell can request open/close through the same state-change path used by parent SDK commands. Resize requests remain bounded by the SDK.

## Build Size

Current production widget build after TASK-065B1:

- JS gzip: 17.62 KB
- CSS gzip: 2.11 KB

Both remain under the B1 budgets.

## Tests

Added/updated tests cover:

- colour parsing and contrast
- token derivation and CSS variable projection
- light/dark/auto theme behavior
- invalid colour fallback in token derivation
- launcher/panel/header/viewport/footer structural rendering
- unavailable state and render error boundary
- store subscription cleanup
- no token in rendered DOM
- browser shell accessibility
- dark token browser flow
- invalid config fail-closed behavior
- desktop/mobile bounds

## Current Exclusions

Welcome, suggestions, messages, composer, citations, privacy content, full focus trap, final responsive polish, visual regression, telemetry, Markdown, lead capture, and backend changes remain deferred.

## TASK-065B2 Note

The iframe visual layer now includes a configured welcome state, suggested-question direct send, in-memory conversation presentation, user/assistant message states, fallback and low-confidence labels, retryable failure presentation, and foundational scrolling/live-region behavior. Free-text composer, citation disclosure, full recovery workflows, and Markdown rendering remain deferred.

## TASK-065B3 Update

The structural shell now includes the functional composer footer, privacy notice, citation disclosure, recovery notices, and focus-boundary behavior. Design-token usage remains centralised and the loader SDK remains framework-free.
