# Current Sprint

Current phase: Sprint 3D - Embeddable Widget
Current task: TASK-064A - Embeddable Widget SDK Architecture

## Active Objective

Design the embeddable browser SDK and iframe delivery architecture for the future Yoranix website-chat widget.

## Guardrails

- Architecture and planning only.
- Do not implement SDK packages, iframe pages, widget UI, build config, backend endpoints, analytics, public history, or package publishing.
- Loader SDK and visual widget are separate components.
- Iframe owns public config/session/message API calls.
- Public session tokens must never enter host-page JavaScript context.
- SDK/iframe communication must use strict versioned postMessage contracts.

## Definition Of Done

- Planning task exists.
- Architecture document exists.
- ADR-0014 exists.
- SDK/UI boundaries, lifecycle, postMessage, session storage, iframe sandbox, CSP, accessibility, versioning, performance, threat/failure models, diagrams, and implementation split are documented.
- `git diff --check` passes.