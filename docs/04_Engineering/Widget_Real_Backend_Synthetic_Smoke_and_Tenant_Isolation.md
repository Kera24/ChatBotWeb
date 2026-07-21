# Widget Real-Backend Synthetic Smoke and Tenant Isolation

Status: Implemented for TASK-066B2

## Purpose

This verification gate proves that the public widget backend works end-to-end with deterministic synthetic tenants and synthetic knowledge data before controlled pilot enablement.

It is not a production deployment, not an uptime monitor, and not a customer-data test.

## Test Environment

The suite lives under `tests/widget-real-backend/` and runs through:

```bash
npm run widget:real-backend:api
npm run widget:pilot:verify
```

The default environment is an isolated in-memory SQLite database created by the test fixture. It uses the real FastAPI application, real public widget routes, real session validation, real idempotency, real origin checks, and real tenant-scoped retrieval fallback.

## Safety Guard

Fixture setup is blocked unless:

- `WIDGET_REAL_BACKEND_TEST=1`
- `APP_ENV` or `NODE_ENV` is `test`, `testing`, or `synthetic-test`
- the database URL is isolated SQLite for the default local suite

The guard rejects production-like, staging-like, customer-like, PostgreSQL, and external database URLs. Fixture cleanup is scoped to the isolated test database; the suite does not run broad destructive cleanup.

## Synthetic Tenants and Widgets

The suite creates two synthetic tenants:

- Alpha tenant with Alpha widget
- Beta tenant with Beta widget

Each widget has:

- a unique public key
- a distinct allowed origin
- a distinct bot name and welcome message
- a distinct primary colour
- a published widget configuration
- one synthetic retrieval-ready document chunk

The fixtures are marked with `synthetic-widget-b2` and contain no PII or customer data.

## Synthetic Knowledge Corpus

Alpha corpus:

```text
The Alpha Observatory operates the Aurora chamber at Meridian Base.
```

Beta corpus:

```text
The Beta Archive maintains the Cobalt library at Harbor Station.
```

The phrases are intentionally distinct so positive retrieval and negative cross-tenant retrieval assertions are unambiguous.

## Provider and Retrieval Strategy

Real components:

- FastAPI app and routing
- public widget config/session/message endpoints
- public credential lookup
- origin validation
- anonymous session validation
- idempotency records
- tenant/workspace/widget scoping
- SQLite-backed vector search fallback
- public output sanitisation
- citation projection

Substituted component:

- external AI provider, replaced by the existing deterministic mock provider

Embedding strategy:

- synthetic chunks are prepared with existing local mock embedding metadata
- SQLite fallback vector search applies organisation, workspace, document, version, chunk status, provider, model, and dimension filters

The deterministic provider does not prove tenant isolation by itself. Tenant isolation is asserted at retrieval and citation boundaries.

## API Smoke Coverage

The API suite verifies:

- Alpha and Beta public config responses
- `ETag`
- `Vary: Origin`
- conditional `304`
- cross-key ETag isolation
- origin denial
- unknown public key denial
- session creation
- `Cache-Control: no-store` for sessions/messages
- no `Set-Cookie`
- message send
- idempotent duplicate handling
- CORS preflight behaviour

## Tenant and Session Isolation

The suite asserts:

- Alpha token cannot be used against Beta widget routes.
- Beta token cannot be used against Alpha widget routes.
- invalid tokens are rejected.
- public sessions remain bound to the correct credential.
- messages persist only under the expected synthetic tenant/workspace.
- duplicate idempotency returns the stored safe response without creating new messages.

## Retrieval Isolation

Positive cases:

- Alpha asks the Alpha fact and receives only Alpha citation data.
- Beta asks the Beta fact and receives only Beta citation data.

Negative cross-tenant cases:

- Alpha asks the Beta-only fact and receives no Beta title, quoted text, or citation.
- Beta asks the Alpha-only fact and receives no Alpha title, quoted text, or citation.

Citation responses are checked for absence of internal IDs, vector scores, document-version IDs, and storage paths.

## Token and Storage Isolation

The API suite verifies response-level token isolation and no-cookie behaviour. Browser-level token isolation remains covered by the existing widget browser security suite. A production-deployed browser real-backend synthetic smoke remains a future extension once a stable real backend target is available.

## Pilot Verification Report

`npm run widget:pilot:verify` writes:

```text
artifacts/widget-pilot-verification/report.json
```

The report includes release metadata when a B1 release manifest exists and safe aggregate pass/fail fields for config, session, message, retrieval, tenant isolation, session isolation, origin isolation, token isolation, and cache isolation.

The report must not include session tokens, message bodies, answers, raw DB credentials, provider prompts, or customer data.

## CI Strategy

The suite is deterministic and does not require external AI credentials. It can run in CI after `npm run widget:release:build` as part of `npm run widget:pilot:verify`.

If future work adds a browser real-backend smoke against a running API service, that browser path should remain separate from the existing mock browser security suite and should use the same synthetic fixture policy.

TASK-066B3 evaluated adding a lightweight live FastAPI browser smoke. It remains deferred because the current browser harness is intentionally mock-backed and a real API subprocess with isolated database fixtures would be a broader environment harness change. The required controlled-pilot gate remains: run B2's API-level real-backend synthetic suite locally/CI, then run a post-deploy real browser smoke against the target staging or pilot environment before tenant enablement.

## Residual Limitations

- No production infrastructure is deployed.
- No external CDN, WAF, or uptime monitor is exercised.
- Browser real-backend smoke is not yet wired to a deployed real API origin.
- PostgreSQL/pgvector migration-backed smoke remains a future environment extension.
- The external AI provider is intentionally deterministic and local.
- Automated tests do not replace manual production pilot validation.

## TASK-066B3 Operational Controls

TASK-066B3 adds provider-neutral operational controls for controlled pilot readiness: `/health/live`, `/health/ready`, safe request correlation IDs, privacy-preserving redaction helpers, in-memory operational counters for test evidence, server-side pilot allowlist controls, global/widget/message kill switches, provider-neutral alert definitions, a dry-run rollback planner, and `npm run widget:pilot:readiness`. It does not deploy production infrastructure or add a monitoring vendor.

## TASK-067B4 Update

Knowledge scope selection is now revision-bound for administration. Real-backend tenant isolation tests should include selected-scope retrieval and rollback-restored scope in TASK-067B5 hardening.

## TASK-067B5 Admin Gate Cross-Reference

Widget administration controlled-pilot use now has its own gate: `npm run widget:admin:release:verify`. B2 real-backend verification remains the public widget tenant/session/retrieval isolation gate and is consumed by the admin readiness report; it is not replaced by admin UI tests.
