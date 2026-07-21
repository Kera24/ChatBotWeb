# Widget SDK Build and Package

TASK-064B1 adds the standalone TypeScript foundation package for the future Yoranix embeddable widget loader.

## Package Purpose

`packages/widget-sdk` is the browser SDK package boundary. It currently provides configuration validation, environment resolution, version constants, public error contracts, build outputs, and tests.

It does not mount an iframe, call public APIs, store sessions, implement postMessage, expose the final `window.YoranixWidget` lifecycle API, or render widget UI.

## SDK/UI Separation

The SDK package is separate from the future visual widget app. The SDK will own bootstrap, configuration parsing, iframe mounting, lifecycle, and strict transport. The iframe app will own public config/session/message API calls and visual interaction.

## Package Structure

```text
packages/widget-sdk/
  package.json
  tsconfig.json
  tsconfig.build.json
  vite.config.ts
  README.md
  scripts/check-size.mjs
  src/
    index.ts
    config.ts
    constants.ts
    errors.ts
    environment.ts
    version.ts
  test/
```

## Build Approach

The package uses Vite library mode because it is lightweight, already aligned with the repository's frontend test tooling, and can produce browser-ready library artifacts without React.

Build output:

- `dist/index.js` - tree-shakeable ESM.
- `dist/yoranix-widget-sdk.global.js` - minified IIFE foundation bundle using `YoranixWidgetSDK` as the bundler global.
- `dist/index.d.ts` and declaration maps.
- Source maps for development.

`dist/` is ignored by Git.

## Scripts

From the repository root:

```bash
npm run widget-sdk:install
npm run widget-sdk:test
npm run widget-sdk:lint
npm run widget-sdk:build
npm run verify
```

`npm run verify` includes Docker Compose config validation, API tests, web tests/lint/build, and SDK tests/lint/build.

## Version Constants

Central constants live in `src/version.ts`:

- `SDK_VERSION`
- `SDK_MAJOR_VERSION`
- `WIDGET_PROTOCOL_VERSION`
- `PUBLIC_CONFIG_SCHEMA_VERSION`
- `PUBLIC_MESSAGE_SCHEMA_VERSION`
- `BUILD_MODE`

Protocol versioning remains separate from package versioning.

## Configuration Contract

`WidgetSDKConfig` allows:

- `widgetKey`
- `environment`
- `initialOpen`
- `mountMode`
- future-compatible `container`
- `localeHint`
- `debug` for development only
- development/test-only `sdkHost` and `iframeHost`
- `nonce`

It rejects unknown fields and does not include tenant IDs, session tokens, model/provider/prompt controls, Origin overrides, security/rate/policy overrides, arbitrary iframe URL, or arbitrary HTML/CSS/JavaScript.

## Environment Mapping

Environment defaults are centralised:

- development: localhost placeholders
- staging: `https://widget-staging.yoranix.com`
- production: `https://widget.yoranix.com`

Production and staging require HTTPS. Runtime host overrides are development-only and reject credentials/userinfo.

## Error Contracts

`WidgetSDKError` exposes safe public fields:

- `code`
- `message`
- `retryable`
- `phase`
- optional safe metadata

Internal causes are retained internally and omitted from `toPublicJSON()`.

## Size Budgets

Initial gzip budgets:

- ESM foundation: <= 10 KiB gzip.
- IIFE foundation: <= 12 KiB gzip.

`npm run widget-sdk:build` runs `scripts/check-size.mjs` after build.

Current TASK-064B1 build result:

- `index.js`: about 2.2 KiB gzip.
- `yoranix-widget-sdk.global.js`: about 2.1 KiB gzip.

## Tests

Vitest covers:

- valid and invalid configuration
- environment/prefix compatibility
- production override rejection
- development override acceptance
- URL and userinfo rejection
- locale/debug/unknown field validation
- immutable environment resolution
- safe error serialisation
- version exports
- ESM/IIFE/declaration build smoke
- no Node built-ins in browser bundle
- size budget

Tests make no network calls, do not require Docker, and do not mutate global browser state permanently.

## Current Non-Functional Status

This package is a build and type foundation only. It does not yet provide an installable customer loader, iframe runtime, postMessage protocol implementation, public API client, session storage, telemetry, or visual UI.
## Iframe Shell And Handshake Foundation

TASK-064B2 adds a dedicated non-visual iframe app at `apps/widget` and shared protocol modules under `packages/widget-sdk/src/protocol`.

Root commands:

```bash
npm run widget:install
npm run widget:test
npm run widget:lint
npm run widget:build
```

The SDK package now also exports a pure iframe URL builder, recommended iframe attributes, protocol validators, and an internal SDK-side handshake controller. The iframe app consumes the same shared protocol definitions, validates `parent_origin`, checks `document.referrer` where available, rejects wildcard target origins, and renders only loading/ready/unavailable status text.

Still out of scope: public API calls, session storage, visual widget UI, launcher, chat panel, final global lifecycle API, and telemetry.

## Widget SDK Lifecycle Runtime

TASK-064B3 adds the public browser lifecycle API, one-instance runtime, iframe mounting, and command acknowledgement handling.

See `docs/04_Engineering/Widget_SDK_Lifecycle_and_Mounting.md` for API details and `examples/widget-host/index.html` for a local smoke host.

The SDK still does not call public backend APIs, store session tokens, render the final widget UI, or send messages.
