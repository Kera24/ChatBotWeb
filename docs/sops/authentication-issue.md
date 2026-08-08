# SOP: Authentication Issue

## Purpose

Respond to an authentication/session/RBAC problem without weakening the auth model to work around it.

## When to use

Login failures, session issues, or RBAC-permission discrepancies reported or observed.

## Step-by-step process

1. Distinguish: authentication failure (can't establish a session) vs. authorization failure (session valid, but RBAC denies an action they should have) vs. a security incident (unauthorized access succeeded) — the last routes to `docs/sops/security-incident.md` instead.
2. For authentication failures: check session cookie (`yoranix_session`) issuance/validation path; check the dev-header fallback isn't accidentally active in production (`docs/engineering/authentication.md`).
3. For authorization failures: verify the user's actual membership/role against what `require_organisation_role({...})` expects — this is usually a data issue (wrong role assigned) not a code issue.
4. Never add a workaround that bypasses `require_organisation_role`/`require_super_admin` to unblock a specific user — fix the underlying role/membership data or the dependency's logic itself.
5. If the stubbed email-delivery gap (`docs/engineering/authentication.md`'s known interim state) is the actual blocker (e.g. password reset), that's a known limitation, not a bug — route to product/roadmap, not an emergency fix.

## Validation

`docs/checklists/security-checklist.md`'s RBAC verification; the specific user's access now matches their intended role.

## Rollback

Revert any auth-path code change via standard deploy rollback; role/membership data corrections don't need a "rollback" in the code sense.

## Success criteria

Root cause correctly classified (auth vs. authz vs. security incident); fixed via correct data or correct logic, never a bypass; no new RBAC gap introduced.
