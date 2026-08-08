# SOP: Rollback

## Purpose

Revert a production deployment safely when it's found to be broken or harmful, per `docs/adr/0018`'s artifact-specific rollback model (still valid under the VPS deployment target — `docs/adr/0027-vps-first-controlled-pilot-hosting.md`).

## When to use

Any post-deploy anomaly attributable to the release, a failed smoke check, or a runbook (`docs/runbooks/`) directing rollback as the recovery step.

## Step-by-step process

1. Identify the specific artifact to roll back: API container image, web container image, widget SDK/iframe (major-alias repoint vs. artifact-manifest redeploy), or — rarely — a database migration.
2. API/web rollback: deploy the previous container image revision.
3. Widget rollback: SDK repoints the major alias to the previous immutable semantic version; iframe redeploys the previous static artifact manifest.
4. Database rollback is avoided as a routine mechanism — migrations are expected to be backward-compatible; if a rollback truly requires a schema reversal, treat it as its own database migration (`docs/sops/database-migration.md`), not an automatic revert.
5. Run post-rollback smoke checks (mandatory).

## Validation

Post-rollback synthetic smoke checks pass; `/observability` dashboard confirms the anomaly has stopped.

## Rollback

Not applicable (this SOP is itself the rollback procedure).

## Success criteria

Previous known-good state restored; smoke checks pass; incident captured for post-incident review (`docs/runbooks/*.md`'s "Post-incident review" section).
