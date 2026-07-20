# TASK-066B2 — Real-Backend Synthetic Smoke, Tenant Isolation, and Pilot Release Verification

Status: Implemented

## Objective

Create a deterministic real-backend verification gate for the embeddable widget using synthetic tenants, synthetic widgets, and synthetic knowledge data.

The gate verifies the production-style widget release path against the real public widget backend routes without production infrastructure, customer data, live AI providers, monitoring vendors, admin UI, or product changes.

## Scope

Implemented:

- Isolated real-backend API smoke suite.
- Synthetic Alpha/Beta tenants and widgets.
- Synthetic tenant-distinct knowledge chunks.
- Destructive-safety guard for integration fixture setup.
- Config, session, message, origin, cache, CORS, session-token, cross-widget, and retrieval-isolation assertions.
- Pilot verification command and machine-readable report.
- Production artifact inspection extension for B2 synthetic/test-only identifiers.
- Pilot verification documentation and checklist updates.

Not implemented:

- Production deployment.
- Production DNS/CDN/WAF/monitoring.
- External real-backend uptime monitor.
- Admin/publishing UI.
- Product analytics or telemetry.
- Live AI-provider smoke.
- Customer production data tests.

## Verification Contract

The suite must run only in a synthetic test context and must reject production-like database/environment inputs.

The current implementation exercises:

- Real FastAPI application routes.
- Real public widget configuration endpoint.
- Real public widget session endpoint.
- Real public widget message endpoint.
- Real public session validation and idempotency logic.
- Real tenant/workspace/widget lookup.
- Real SQLite-backed tenant-scoped retrieval fallback.
- Existing deterministic mock AI provider.
- Existing local mock embedding metadata path.

The external generative provider is substituted by the existing deterministic mock provider to avoid network dependency, cost, and nondeterministic output. Tenant isolation is proven at the data/retrieval boundary through synthetic chunk and citation assertions.

## Commands

- `npm run widget:real-backend:api`
- `npm run widget:real-backend:test`
- `npm run widget:pilot:verify`

## Acceptance Notes

Passing `npm run widget:release:build` alone is insufficient for controlled pilot deployment. A pilot gate must also pass `npm run widget:pilot:verify`.

Next task:

TASK-066B3 — Widget Operational Controls, Health Checks, Privacy-Preserving Observability, Alerts, Rollback, and Pilot Enablement
