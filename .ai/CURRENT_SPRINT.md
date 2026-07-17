# Current Sprint

Current phase: Sprint 3E - Widget Experience
Current task: TASK-065B1 - Widget Rendering Foundation, Design Tokens, and Structural Shell

## Active Objective

Implement the Preact rendering foundation, design-token system, customer-brand mapping, and structural launcher/panel/header shell for the iframe widget app.

## Guardrails

- Preact is allowed only inside `apps/widget`.
- The loader SDK remains framework-free.
- Public API calls, session storage, message service, and state store remain framework-independent.
- Session tokens must not enter component props, context, DOM, postMessage, debug output, or host callbacks.
- Do not implement full welcome state, suggestions, message thread, composer, citations, privacy/terms content, final motion polish, telemetry, lead capture, Markdown rendering, or backend changes.

## Definition Of Done

- Structural Preact shell renders after secure bootstrap/config loading.
- Tokens, branding, contrast, light/dark/auto theme behavior, launcher/panel/header/viewport/footer, safe asset boundary, accessibility foundation, and resize/lifecycle integration are tested.
- Existing browser security tests remain passing.
