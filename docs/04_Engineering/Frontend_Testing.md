# Frontend Testing

Version: 0.1
Status: Implemented

## Stack

The dashboard uses a lightweight unit and component testing stack:

- Vitest for the test runner
- React Testing Library for component behaviour
- Testing Library user-event for keyboard and control interaction
- jsdom for DOM execution
- Testing Library DOM matchers through `@testing-library/jest-dom`

Cypress, Playwright, visual regression testing, and browser end-to-end testing are outside the current scope.

## Locations

Configuration lives in:

- `apps/web/vitest.config.ts`
- `apps/web/test/setup.ts`
- `apps/web/test/test-utils.tsx`

Tests are colocated with the code they cover, for example:

- `apps/web/lib/api/*.test.ts`
- `apps/web/lib/auth/*.test.ts`
- `apps/web/components/conversations/*.test.tsx`

## Commands

From the repository root:

```bash
npm run web:test
npm run web:lint
npm run web:build
npm run verify
```

From `apps/web`:

```bash
npm run test
npm run test:run
npm run lint
npm run build
```

`npm run verify` runs Docker Compose configuration validation, API tests, frontend tests, frontend lint, and the frontend production build.

## Mocking Approach

Frontend tests must not call a live backend. API tests mock `globalThis.fetch` and assert the requested URL, tenant query parameters, error mapping, and development dashboard headers. Component tests use local typed fixtures for conversation summaries, messages, citations, and error states.

Public-widget clients are intentionally absent from this foundation. Dashboard development headers are tested only through the dashboard API layer and must not be reused by future public-widget code.

## Component Testing Conventions

Prefer behavioural assertions over snapshots:

- Query by role, label, heading, or visible text.
- Assert links, form state, and status labels directly.
- Keep fixtures small and tenant-explicit.
- Avoid assertions on decorative CSS details unless they carry accessibility meaning.

Conversation-history tests cover the API client, development session validation, list rendering, filters, pagination, shared state panels, message threads, citations, badges, and allowed technical metadata.

## Accessibility Expectations

Tests should cover the basics that protect the dashboard experience:

- Semantic headings for page and state panels.
- Labelled filters and controls.
- Keyboard-usable buttons and links.
- Status and answer-state text that is not colour-only.
- Collapsible technical details with clear summary text.
- Citations visible without hover-only interaction.

Large automated accessibility platforms are outside this task; they can be added later if the workflow needs deeper checks.

## Out Of Scope

The current testing foundation does not add product behaviour, production authentication, analytics, public widget testing, real backend calls, browser E2E tests, or visual regression tests.
