# Current Sprint

Current phase: Sprint 3E - Widget Experience
Current task: TASK-065A - Widget UI and Interaction Architecture

## Active Objective

Design the complete visual, interaction, accessibility, responsive, and implementation architecture for the embeddable Yoranix website-chat widget before any visual UI implementation begins.

## Guardrails

- Do not implement Preact/React/framework dependencies, widget components, CSS, launcher, panel, composer, message thread, citation disclosure, animations, visual assets, backend changes, SDK changes, telemetry, lead capture, public history, or Markdown rendering in TASK-065A.
- The loader SDK remains framework-free.
- Public config/session/message API calls remain iframe-owned.
- Public session tokens must never enter host-page JavaScript, iframe URLs, postMessage, logs, telemetry, or public state snapshots.
- Backend public message output is currently sanitised plain text plus safe citations; the UI must render defensively and not assume Markdown.
- Widget UI implementation must be split across TASK-065B1 through TASK-065B4.

## Definition Of Done

- UI/SDK/backend boundaries are explicit.
- User journeys, component hierarchy, design-token mapping, accessibility/focus model, responsive/motion system, message/citation/composer/error states, testing strategy, threat/failure models, diagrams, ADR, and implementation split are documented.
- No runtime UI code or dependency changes are added.
