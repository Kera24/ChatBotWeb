# Widget Browser Integration Tests

This package contains Playwright tests for the embeddable widget browser boundary.

Required local ports:

- Host page: `http://127.0.0.1:4100`
- Widget iframe: `http://127.0.0.1:4200`
- Mock public API: `http://127.0.0.1:4300`

Commands:

```bash
npm run widget:e2e:install
npm run widget:e2e:chromium
npm run widget:e2e:extended
```

The required verification suite runs Chromium only. Firefox and WebKit are available through the extended command because full three-browser installation and execution is heavier for every normal verification run.

The suite serves real built SDK and widget artifacts and uses a mock public API matching the public endpoint contracts. No production credentials or backend services are required.