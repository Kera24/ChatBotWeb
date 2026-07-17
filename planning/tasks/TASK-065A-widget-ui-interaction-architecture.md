# TASK-065A - Widget UI and Interaction Architecture

Status: Planning
Phase: Sprint 3E - Widget Experience

## Objective

Design the complete visual, interaction, accessibility, responsive, and implementation architecture for the embeddable Yoranix website-chat widget. This task is architecture, product design, UX, interaction, accessibility, and planning only.

## Sources Read

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- Public widget session, configuration, message/RAG, output sanitisation, SDK, iframe, API client, and browser-security architecture/engineering docs
- ADRs `0011`, `0012`, `0013`, `0014`
- TASK-061B through TASK-064B5 planning and implementation docs
- `docs/05_Design/01_Design_System.md`
- `.ai/context/design-principles.md`
- Current widget app and SDK protocol/runtime source context

## Scope

Create planning artifacts for:

- Visual widget product boundary.
- User journeys and failure/recovery flows.
- Information architecture and component hierarchy.
- Controlled Expressionism design rules.
- Client-branding and design-token model.
- Launcher, panel, header, welcome, suggestions, messages, citations, composer, privacy, and error states.
- Responsive, motion, accessibility, focus, keyboard, and internationalisation architecture.
- Rendering framework decision for future implementation.
- UI threat/misuse review, failure matrix, diagrams, tests, design review gates, and implementation split.

## Non-Goals

Do not implement Preact/React/framework dependencies, widget components, CSS, launcher, panel, composer, message thread, citation disclosure, animations, visual assets, backend changes, SDK changes, telemetry, lead capture, public history, or Markdown rendering.

## Architecture Decision Summary

Use Preact for the iframe visual application while keeping the loader SDK framework-free. Preact gives the visual widget a maintainable component model for accessibility, state, and responsive behaviour while preserving a small iframe bundle and keeping all framework code isolated from the host page.

The backend currently supplies sanitised plain-text answers and safe citations. The UI renders answers and configured text as text, never raw HTML. Restricted Markdown is a future reviewed renderer path, not a TASK-065B assumption.

Customer branding maps only through validated design tokens. Poor brand colours fall back to accessible platform accents. The visual widget targets WCAG 2.2 AA and must not weaken token isolation, iframe-owned API calls, or postMessage boundaries.

## Future Implementation Tasks

- `TASK-065B1` - Preact rendering foundation, design tokens, theme/branding validation, layout shell, launcher/panel structural states.
- `TASK-065B2` - Welcome state, suggested questions, conversation thread, user/assistant message presentation, loading/fallback/error states.
- `TASK-065B3` - Composer, message-service integration, citations, session/offline/rate-limit recovery, focus/accessibility.
- `TASK-065B4` - Responsive/mobile hardening, motion, visual regression, browser/accessibility/security tests, performance optimisation.

## Acceptance Criteria

- UI/SDK/backend boundaries are explicit.
- Complete user journeys are defined.
- Component architecture is defined.
- Design tokens and customer-brand mapping are defined.
- Accessibility target and focus model are complete.
- Message, citation, fallback, error, and composer states are complete.
- Responsive and motion systems are defined.
- Rendering framework decision is recorded in ADR-0015.
- Test and review gates are complete.
- Implementation is split into controlled tasks.
- Threat and failure models are complete.
- No UI runtime code is added.
