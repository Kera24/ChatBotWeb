# Yoranix Widget SDK

Foundation package for the future embeddable Yoranix widget loader.

Current TASK-064B1 status:

- Defines typed configuration, environment resolution, version constants, and SDK error contracts.
- Builds ESM and browser IIFE artifacts with TypeScript declarations and source maps.
- Provides unit tests and bundle size checks.

This package does not yet mount an iframe, call public APIs, store sessions, expose the final `window.YoranixWidget` lifecycle API, use postMessage, or render widget UI.

## Commands

```bash
npm run build
npm run lint
npm run test
```

The IIFE build reserves the future bundler global name `YoranixWidgetSDK`; runtime mutation of `window.YoranixWidget` is intentionally deferred.