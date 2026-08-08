# Authentication, Sessions, and RBAC

## Registration and login

- `app.auth.service.provision_account()` — creates `User` + `Organisation` + a default `Workspace` + a `Membership` (role `org_owner`) + a trial `Subscription` (plan `starter`) in one transaction, plus an audit event. Password hashed with PBKDF2-SHA256 (210k iterations).
- `authenticate_user()` verifies credentials; `create_auth_session()` issues a random token (`secrets.token_urlsafe`), stores only its HMAC-SHA256 hash in `AuthSession` (never the raw token), TTL via `AUTH_SESSION_DAYS`/`AUTH_REMEMBER_SESSION_DAYS`.
- The router (`app/api/v1/auth.py`) sets the raw token in an httponly, `SameSite=Lax` cookie named `settings.AUTH_SESSION_COOKIE_NAME` (`yoranix_session`), `secure` only when `APP_ENV=production`.
- `get_user_for_session_token()` looks up by hash, rejects expired/revoked/inactive sessions.

## Password reset / email verification (known gaps)

`create_password_reset()`/`reset_password()` work end-to-end at the data layer (hashed, time-limited `PasswordResetToken`), but **no email delivery is wired up** — the forgot-password endpoint's own response says so. `GET /verify-email` is a stub; email verification is not enforced anywhere. Do not assume either flow is production-ready without checking current status first.

## Onboarding

`User.onboarding_completed_at`, set once via `POST /api/v1/auth/onboarding/complete`. `requireDashboardSession()` (frontend) redirects incomplete-onboarding users to `/onboarding` for routes that require it, and redirects completed users away from `/onboarding`.

## `requireDashboardSession()` (frontend gate)

`apps/web/lib/auth/session.ts`: server-side, reads the browser's cookie via `next/headers`, calls `GET /api/v1/auth/me` server-to-server, redirects to `/login` on failure, redirects based on onboarding state, then converts the API's `AuthContext` response into a `DashboardSession` (`organisationId`, `workspaceId`, `role`, etc.) via `dashboardSessionFromAuthContext()`.

## Backend current-user resolution — two different dependencies

`apps/api/app/api/deps.py`:

- **`AuthenticatedUserDependency`** (`get_authenticated_user`) — real cookie-only auth, used by `/auth/me`, `/onboarding/complete`. 401s with no valid session cookie. This is the actual production auth mechanism.
- **`CurrentUserDependency`** (`get_development_current_user`) — used by almost every *other* v1 router. First tries the real session cookie (resolves membership role from it); only falls back to `X-Development-User-Email`/`X-Development-Role` headers when no session cookie is present **and** `APP_ENV` is `development`/`test`/`testing` **and** `settings.ALLOW_DEV_AUTH` is explicitly enabled (401s otherwise). `ALLOW_DEV_AUTH` defaults to `false` — this is a deliberate fail-closed gate (P1-2 of the launch-readiness review): `APP_ENV` alone is not a security boundary, since it defaults to `development` and a missing/mistaken value in a real deployment must never silently grant dev-auth access. `assert_dev_auth_policy_safe()` (called once at startup from `app.main.create_app`) additionally refuses to boot if `ALLOW_DEV_AUTH=true` is set outside development/test/testing. Test fixtures enable the flag explicitly via `apps/api/tests/conftest.py`'s autouse `_allow_dev_auth_in_tests` fixture, not by relying on `APP_ENV`'s default. This dual behavior is why so many test fixtures use dev headers directly — it's a deliberate test/dev convenience layered on top of real auth, not a separate insecure path in production.

## RBAC

`require_organisation_role(allowed_roles: set[str])` — dependency factory checking active `Membership.role` in `allowed_roles`, with `super_admin` bypassing the check entirely. Roles: `org_owner`, `client_admin`, `contributor`, `viewer` (org-scoped) + `super_admin` (cross-tenant). See `backend.md` for the module-scope dependency naming convention used across routers.

## Memberships and settings

- `app/api/v1/memberships.py` — list (viewer+), role/status changes (owner/admin only), self-deactivation blocked, audit-logged.
- `app/api/v1/settings.py` — workspace settings are intentionally very limited today: only `workspace.name`/`workspace.default_language` are editable (`EDITABLE_FIELDS`); everything else is read-only/environment-controlled/secret-managed, explicitly enumerated in the API response's `capabilities` block. Do not add new editable settings fields without checking whether they should really be environment-controlled instead.

## Tenant isolation invariant

Every tenant-scoped query filters by `organisation_id` **and** `workspace_id` (not just one). Every tenant-scoped detail-fetch endpoint re-verifies the fetched row's tenant IDs match the caller's context, returning 404 (not 403) on mismatch so a client can never learn whether a resource exists in another tenant. This is enforced per-feature in each repository/route, not by a single central mechanism — when adding a new tenant-scoped resource, copy the pattern from the nearest existing similar resource (e.g. `conversations.py`'s `_ensure_workspace`/`_ensure_assistant` helpers).
