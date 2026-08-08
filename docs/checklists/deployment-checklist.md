# Deployment Checklist

## Required validation

- `npm run verify` for cross-cutting changes (`docs/validation-policy.md`'s decision table) before deploying.
- Migration preflight (`database_migration preflight`) after any schema change, per `docs/architecture/deployment.md`.

## Things to verify

- `docker-compose.prod.yml`, `deployment/caddy/Caddyfile`, backup/restore scripts, `infrastructure/azure/` were not modified without explicit instruction.
- The one-shot `migrate` job runs to head before `api` starts.
- Release identity is recorded (git SHA, image digests) per `docs/releases/`.
- Rollback plan identified before deploying, not improvised after a problem (`docs/sops/rollback.md`).
- CI gate (`.github/workflows/verify.yml`) is green.

## Common mistakes

- Modifying production-safety-critical files as a side effect of an unrelated task.
- Deploying without a pre-identified rollback path.
- Skipping migration preflight after a schema change.

## Required documentation

- `docs/architecture/deployment.md` updated if the deployment topology changes.
- Release recorded per the applicable `docs/releases/*.md` type.

## Definition of Done

CI green; migration preflight clean; rollback plan identified; release identity recorded; no unauthorized production-safety-critical file changes.
