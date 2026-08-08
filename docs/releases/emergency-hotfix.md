# Release Type: Emergency Hotfix

For urgent, narrowly-scoped fixes to production-impacting defects — see `docs/sops/hotfix.md` for the execution procedure this release type gates.

## Entry criteria

A confirmed production-impacting defect that cannot reasonably wait for the next normal release cycle; fix is scoped as narrowly as possible (no bundled unrelated changes).

## Exit criteria

Deployed, smoke-checked, with the specific defect confirmed resolved.

## Evaluation requirements

Evaluation gate required if the fix touches the AI pipeline — hotfix status shortens process overhead, never evaluation rigor. Security review required if the fix is security-relevant.

## Rollback

`docs/sops/rollback.md`, with the hotfix's narrow scope making rollback low-risk by design; this is a primary reason hotfixes must stay narrowly scoped.

## Monitoring

Heightened post-deploy monitoring given the expedited process (less pre-deploy scrutiny is compensated by more post-deploy attention).

## Approval requirements

Expedited approval (one available reviewer, not necessarily the original feature's reviewer), but never zero approval — even genuine emergencies get a second set of eyes before deploy, per `CLAUDE.md`'s git-safety posture on skipping hooks/checks.
