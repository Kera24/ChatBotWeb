# Authentication — Current / Future / Out of Scope

## Current

Cookie-session auth (`yoranix_session`, HMAC-hashed token storage), dev-header fallback for local/test environments (gated by both `APP_ENV` **and** an explicit `ALLOW_DEV_AUTH=true` opt-in, fail-closed by default — see P1-2 of the launch-readiness review), membership-based RBAC (`org_owner`/`client_admin`/`contributor`/`viewer`/`super_admin`). Full detail: `docs/architecture/authentication.md`.

## Future

- **Email delivery** for password reset / verification (currently stubbed — see `docs/architecture/authentication.md`'s "known gaps"). Planned in `docs/roadmap/roadmap.md`'s Production Stabilisation phase.
- **Enterprise SSO** (SAML/OIDC) — see `docs/future/EnterpriseSSO.md`.
- Replacing the "temporary tenant context" query-param pattern (`organisation_id` as an explicit query param on every tenant route) with inference from the authenticated session alone, once production auth is trusted enough to do so safely (this is called out as a deliberate interim state throughout the router code, not an oversight).

## Out of scope (not planned)

- Passwordless/magic-link auth (no current requirement).
- Multi-factor authentication (no current requirement; would be bundled with the SSO/compliance roadmap if requested — see `docs/future/ComplianceRoadmap.md`).
