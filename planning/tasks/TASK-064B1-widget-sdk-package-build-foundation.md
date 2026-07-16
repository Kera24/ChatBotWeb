# TASK-064B1 - Widget SDK Package and Build Foundation

Status: Implemented
Phase: Sprint 3D - Embeddable Widget

## Objective

Create the standalone TypeScript SDK package and build/test foundation for the embeddable Yoranix widget loader.

## Scope

- `packages/widget-sdk` package boundary.
- Vite library build for ESM and browser IIFE output.
- TypeScript declaration generation.
- Version constants.
- Typed SDK configuration contract and deterministic validation.
- Environment resolver.
- SDK error contracts.
- Unit/build tests.
- Root scripts and CI integration.

## Non-Goals

- No iframe mounting.
- No launcher.
- No postMessage runtime.
- No lifecycle/global `window.YoranixWidget` API.
- No public API client.
- No session storage.
- No widget UI or React.
- No telemetry, CDN deployment, SRI generation, backend changes, or npm publishing.

## Acceptance Criteria

- SDK package installs, typechecks, builds, and tests from root scripts.
- ESM, IIFE, declaration, and source-map outputs are generated under ignored `dist`.
- Build size budget passes.
- Public configuration types exclude tenant IDs, session tokens, model/provider/prompt overrides, arbitrary production URLs, and policy overrides.
- Root verification includes SDK tests, lint, and build.