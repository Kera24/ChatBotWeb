# ADR-0015: Widget UI Rendering and Interaction Model

Status: Proposed
Date: 2026-07-17

## Context

The platform now has public widget configuration, anonymous sessions, message/RAG execution, output sanitisation, a framework-free loader SDK, a dedicated iframe shell, iframe-owned API clients, session storage, and browser-level security tests.

The next boundary is the visual chat widget. It must provide a distinctive Yoranix experience while preserving public-channel security: the loader remains separate, public API calls stay inside the iframe, session tokens never cross postMessage, and backend output is currently sanitised plain text with safe citations.

The UI must support controlled Expressionism, customer branding, accessibility, responsive behaviour, failure recovery, and future evolution without weakening tenant isolation or public widget security.

## Decision

Use Preact for the iframe visual application while keeping the loader SDK framework-free.

The visual app will use a component architecture for launcher, panel, header, welcome state, suggestions, conversation thread, messages, citations, composer, errors, privacy/footer, focus management, and responsive layout. Existing iframe services and the framework-free state store remain service boundaries underneath the Preact UI.

The UI will render answers and configured content as text for MVP. It will not use `innerHTML`, arbitrary CSS, raw HTML, or a Markdown renderer in the initial implementation. Future restricted Markdown requires a separately reviewed renderer and must preserve backend and UI sanitisation boundaries.

Customer configuration maps through validated design tokens only. Brand colours influence accents after contrast checks; semantic state colours and focus styles remain platform-owned.

## Alternatives Considered

### A. Continue Framework-Free DOM Rendering

Pros:

- Smallest runtime.
- Matches current widget shell.
- No new rendering dependency.

Cons:

- The planned UI has substantial state, focus, live-region, responsive, and component complexity.
- Manual DOM updates increase regression risk.
- Component testing and visual state coverage become harder.

Rejected for the full visual UI, though framework-free services and SDK runtime remain.

### B. React

Pros:

- Familiar ecosystem.
- Strong component and accessibility testing patterns.

Cons:

- Larger iframe bundle than needed.
- More runtime than the widget requires.

Rejected for MVP iframe UI.

### C. Preact

Pros:

- React-like maintainability with a small runtime.
- Good fit for isolated iframe app.
- Works with existing service/state boundaries.
- Supports component testing without leaking framework code to the host page.
- Keeps loader SDK framework-free.

Cons:

- Adds a dependency to the iframe app.
- Some React ecosystem assumptions do not apply directly.
- Requires bundle-size monitoring.

Chosen.

### D. Lit/Web Components

Pros:

- Strong encapsulation and native custom-element model.

Cons:

- Encapsulation is less valuable inside an iframe.
- Adds custom-element lifecycle complexity.
- Less aligned with the current state/service test strategy.

Rejected.

### E. Svelte

Pros:

- Small compiled output.
- Good component ergonomics.

Cons:

- Introduces a new compiler/framework path.
- Less continuity with React-like dashboard/team patterns.

Rejected.

## Consequences

Positive:

- The visual UI can be implemented as small, testable components.
- Accessibility and focus behaviour can be owned explicitly in the iframe app.
- The loader SDK remains dependency-light and framework-free.
- Preact stays isolated from customer host pages by the iframe boundary.
- Existing browser integration tests can expand into visual and accessibility coverage.

Trade-offs:

- The iframe bundle grows and must be budgeted.
- Preact dependency and build integration must be added in TASK-065B1, not in this architecture task.
- Future restricted Markdown needs a separate rendering/security review.

## Required Controls

- Loader SDK remains framework-free.
- Iframe owns UI rendering and public API calls.
- Session token remains iframe-only.
- UI never sends messages, answers, citations, tokens, or raw config through postMessage.
- Render backend answers and configured text as text, not HTML.
- Customer branding maps through validated design tokens.
- Widget targets WCAG 2.2 AA.
- Focus trap, focus restore, live regions, keyboard operation, reduced motion, contrast fallback, and forced-colours support are required.
- No public history, lead capture, telemetry, file upload, voice, attachments, or Markdown renderer in the first visual implementation.

## Implementation Split

- `TASK-065B1` - Preact rendering foundation, design tokens, theme/branding validation, layout shell, launcher/panel structural states.
- `TASK-065B2` - Welcome state, suggested questions, conversation thread, user/assistant message presentation, loading/fallback/error states.
- `TASK-065B3` - Composer, message-service integration, citations, session/offline/rate-limit recovery, focus/accessibility.
- `TASK-065B4` - Responsive/mobile hardening, motion, visual regression, browser/accessibility/security tests, performance optimisation.

## Non-Goals

This ADR does not implement Preact, components, styles, launcher, panel, composer, message rendering, citations, animations, assets, SDK changes, backend changes, telemetry, lead capture, public history, or Markdown rendering.

## Related Documents

- `implementation-pack/05_Design/02_Widget_UI_Interaction_Architecture.md`
- `implementation-pack/02_Architecture/09_Embeddable_Widget_SDK_Architecture.md`
- `implementation-pack/02_Architecture/08_Public_Widget_Message_RAG_Architecture.md`
- `docs/adr/0013-public-widget-message-rag-boundary.md`
- `docs/adr/0014-widget-sdk-and-iframe-delivery.md`
- `docs/04_Engineering/Widget_Iframe_API_Client_and_Session_Storage.md`
- `docs/04_Engineering/Widget_Browser_Integration_and_Security_Testing.md`
- `planning/tasks/TASK-065A-widget-ui-interaction-architecture.md`
