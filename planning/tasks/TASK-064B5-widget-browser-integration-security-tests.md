# TASK-064B5 - Widget Browser Integration and Security Tests

Status: In progress

Scope:
- Add Playwright browser integration/security tests for the embeddable widget boundary.
- Serve real built SDK and iframe artifacts across separate local origins.
- Validate token isolation, strict postMessage behavior, iframe-owned API calls, storage, lifecycle, CORS/CSP, sandbox, responsive, focus, accessibility-shell, and hostile-host scenarios.

Constraints:
- No visual chat UI.
- No host-page sendMessage API.
- No backend feature changes.
- Test-only iframe hooks must remain test-mode only and must not expose session tokens.