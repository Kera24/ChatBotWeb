# Current Sprint

Current phase: Sprint 3D - Embeddable Widget
Current task: TASK-064B1 - Widget SDK Package and Build Foundation

## Active Objective

Create the standalone TypeScript SDK package and build/test foundation for the embeddable Yoranix widget loader.

## Guardrails

- Do not mount an iframe.
- Do not call public APIs.
- Do not implement postMessage, lifecycle runtime, global init/open/close APIs, session storage, widget UI, telemetry, backend changes, or publishing.
- Keep the SDK package React-free and dependency-light.
- Public configuration must not accept tenant IDs, session tokens, AI overrides, Origin overrides, security-policy overrides, or arbitrary production hosts.

## Definition Of Done

- `packages/widget-sdk` package exists.
- ESM/IIFE/declaration builds work.
- Typed config, environment, version, and error contracts exist.
- SDK tests/lint/build run from root scripts.
- Root verify and CI include SDK checks.
- Documentation is updated.