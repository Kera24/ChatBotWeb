# Runbook: Authentication Outage

## Symptoms

Users unable to log in or sessions failing validation platform-wide.

## Diagnosis

1. Check session-cookie issuance/validation path (`yoranix_session`) for errors.
2. Confirm the dev-header fallback isn't accidentally active/interfering in production (`docs/engineering/authentication.md`).
3. Check if this is total (nobody can log in) or partial (specific role/tenant affected — more likely an RBAC data issue than an outage).

## Recovery

1. If correlated with a recent deploy touching auth code: `docs/sops/rollback.md` immediately — authentication is not a subsystem to "fix forward" under pressure.
2. If a session-signing key or config issue: verify `Settings` auth-related config hasn't drifted.
3. Confirm this isn't actually a security incident (unauthorized access, not just failed legitimate access) — if it is, switch to `docs/sops/security-incident.md`.

## Validation

Login succeeds for a test account across affected roles; session validation confirmed working.

## Escalation

If root cause isn't immediately clear, prioritize rollback over continued live debugging — auth is maximally user-impacting.

## Post-incident review

Was this caught by pre-deploy testing? If not, `docs/checklists/security-checklist.md`'s RBAC verification needs strengthening.
