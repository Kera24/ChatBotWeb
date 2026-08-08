# Release Type: Beta

For functionality exposed to a broader tenant subset (opted-in or selected), expected to be stable but not yet fully validated at scale.

## Entry criteria

Full evaluation gate passes with no regressions; all applicable `docs/checklists/*.md` items satisfied; security validation complete.

## Exit criteria

Sustained stable operation across the beta group for a defined observation period, with no unresolved critical issues.

## Evaluation requirements

Full evaluation gate, plus advisory grader review actively monitored (not just run) — beta is the stage where grader-dimension trends start informing go/no-go decisions even though they remain formally advisory.

## Rollback

`docs/sops/rollback.md`; beta tenants are informed of the rollback and any data/behavior implications.

## Monitoring

Active dashboard monitoring for the full beta period; alerts configured and attended to, not just logged.

## Approval requirements

Reviewer sign-off plus confirmation every `docs/production/readiness-gates.md` item applicable to beta scope is satisfied.
