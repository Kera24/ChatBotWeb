# Enterprise SSO

## Purpose

Support SAML/OIDC single sign-on for enterprise tenants, alongside the current cookie-session auth.

## Current limitation

`docs/engineering/authentication.md` — cookie-session auth with membership-based RBAC only; no SAML/OIDC identity provider integration exists.

## Why postponed

No current tenant requires it; building SSO before it's needed adds real complexity (per-tenant IdP configuration, SAML/OIDC protocol handling, session-model changes) with no corresponding evaluation-backed benefit. Bundled conceptually with `docs/future/ComplianceRoadmap.md` since enterprise buyers requesting SSO typically also need compliance controls together.

## Dependencies

- A concrete enterprise tenant requirement (sales/support-driven), not speculative build.
- `docs/engineering/authentication.md`'s existing membership/RBAC model must stay the source of truth for authorization even when SSO changes authentication.

## Implementation phases

1. Add a pluggable identity-provider abstraction alongside existing cookie-session auth (not a replacement — most tenants keep the current model).
2. Support one SAML or OIDC provider end-to-end for a pilot enterprise tenant.
3. Generalize to a per-organisation configurable IdP once the first integration is proven.
4. Map IdP group/role claims onto the existing `org_owner`/`client_admin`/`contributor`/`viewer` RBAC roles — no new authorization model, just a new authentication front-end for it.

## Technical design

New `app.auth.sso.*` module; session issuance still produces the same `yoranix_session` cookie/token the rest of the system already understands — SSO changes *how* a session is established, not what a session *is*.

## Evaluation plan

Security review of the SAML/OIDC integration (this is a security-sensitive surface) before any pilot tenant is enabled; verify RBAC mapping produces identical permission behavior to the existing manual-membership model.

## Rollback strategy

Per-tenant opt-in; a tenant's existing cookie-session auth path remains fully functional and is not modified by SSO's addition, so disabling SSO for a tenant has zero effect on others.

## Success metrics

At least one enterprise tenant successfully using SSO with correct RBAC mapping and no authentication-security regressions.
