# Release Checklist

## Required validation

- Every gate in `docs/production/readiness-gates.md` satisfied for the applicable release type (`docs/releases/`).

## Things to verify

- Tests, evaluation, guardrails, observability, documentation, rollback plan, performance, and security are all explicitly signed off, not assumed.
- The release type (internal/alpha/beta/production/enterprise/hotfix) matches its defined entry/exit criteria in `docs/releases/`.
- Approval requirements for the release type are actually satisfied (not just "someone looked at it").

## Common mistakes

- Treating a production release's gate the same as an internal release's (internal releases have looser gates by design — don't over- or under-apply them).
- Shipping a hotfix through the full release process when `docs/releases/emergency-hotfix.md`'s expedited path is what's needed (and vice versa — using the hotfix path for a non-emergency change).

## Required documentation

- Release recorded in the applicable `docs/releases/*.md` type's log/record (release identity, approver, date).

## Definition of Done

Every applicable gate satisfied and recorded; correct release type used; approval obtained per that type's requirements.
