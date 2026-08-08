# SOP: Deploying

## Purpose

Ship an approved release to production safely, per `docs/architecture/deployment.md`'s VPS Docker Compose model.

## When to use

Any production deployment, following Release Approval in `docs/workflows/engineering-lifecycle.md`.

## Step-by-step process

1. Confirm CI (`.github/workflows/verify.yml`) is green on the release commit.
2. Run migration preflight if the release includes a schema change.
3. Deploy via `docker-compose.prod.yml` (`api`, `web`, `widget-assets`, `caddy`); the one-shot `migrate` job runs to head before `api` starts.
4. Run post-deploy smoke checks against the live environment.
5. Monitor per `docs/checklists/production-checklist.md` for the appropriate window.
6. Record release identity (git SHA, image digests) per `docs/releases/`.

## Validation

Smoke checks pass; `/observability` dashboard shows healthy traces for the new deployment; no CI failures.

## Rollback

If smoke checks fail or an anomaly is detected, execute `docs/sops/rollback.md` immediately — don't attempt to "fix forward" under production pressure.

## Success criteria

Deployment completes, smoke checks pass, monitoring window clean, release identity recorded.
