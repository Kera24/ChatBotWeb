# Widget Browser Integration and Security Testing

TASK-064B5 adds a Playwright browser test foundation for the embeddable widget boundary before visual UI development.

## Architecture

The browser suite lives in `tests/widget-browser` and uses three deterministic local origins:

- Host page: `http://127.0.0.1:4100`
- Widget iframe and SDK assets: `http://127.0.0.1:4200`
- Mock public API: `http://127.0.0.1:4300`

The tests serve real built SDK and widget artifacts. The mock API implements public config, session, message, and preflight routes with contract-shaped responses. It is not a replacement for backend endpoint tests; it validates browser behavior and the iframe-owned client boundary.

## Browser Matrix

Required verification runs Chromium.

Firefox and WebKit are available through `widget:e2e:extended`, but they are not part of normal `verify` because installing and running all three browsers is heavier than the current deterministic smoke requirement.

## Test-Mode API Host

The iframe app supports a compile-time test-mode API host through `apps/widget/.env.test` and `vite build --mode test`.

Production builds do not accept this override from the host page. The host SDK still cannot provide arbitrary API hosts in production configuration.

## Coverage

The Chromium suite covers:

- Real SDK loader to iframe mount and handshake.
- Config fetch after handshake and before `widget_ready`.
- Lazy first-message session creation.
- Message idempotency header generation.
- Session reuse from iframe-origin storage.
- Token isolation from host globals, SDK public API, iframe URL, parent DOM, postMessage, console, host storage, localStorage, and cookies.
- Token presence only in iframe-owned storage/private state and message API request body.
- Exact-origin postMessage behavior and forged message rejection.
- Hostile-host storage access denial.
- CORS Origin, no cookies, approved headers, and no wildcard assumptions.
- CSP supported and blocked cases.
- Sandbox and permission attributes.
- Lifecycle open/close/destroy, focus restore, responsive bounds, and closed-state host interaction.
- Accessible shell status semantics.
- Safe logging checks.

## Commands

```bash
npm run widget:e2e:install
npm run widget:e2e:chromium
npm run widget:e2e:extended
```

`npm run verify` includes the Chromium browser suite and then rebuilds the production widget app to ensure the normal production artifact is restored after the test-mode build.

## Artifacts

Playwright keeps traces and screenshots only on failure. Test data uses fake public keys and fake session tokens, but assertions still prevent token-like values from appearing in host-visible surfaces.

## Limitations

- The suite uses a mock public API, not a real backend seed.
- The test-only iframe harness exists only in Vite `test` mode and is used because the final message UI does not exist yet.
- No visual launcher, chat panel, composer, Markdown renderer, citation UI, telemetry, or analytics are tested in TASK-064B5.
- Full cross-browser execution is available but not required for every normal verification run.
## TASK-065B1 Browser Coverage

The browser suite now validates the structural Preact shell, including launcher accessibility, panel semantics, dark configuration tokens, invalid-colour response fail-closed behavior, viewport bounds, and continued token isolation.
