# Prompt Template: Deployment

Use this when the task touches Docker Compose, Caddy, backup/restore, or Azure infrastructure. **High blast-radius area — confirm explicit instruction before making any change here, and never commit/push/deploy without being asked.**

## Scope

`docker-compose*.yml`, `deployment/**`, `apps/api/Dockerfile`, `apps/web/Dockerfile`, `infrastructure/azure/**`. See `docs/architecture/deployment.md`.

## Constraints

- Never modify `docker-compose.prod.yml`, `deployment/caddy/Caddyfile`, backup/restore scripts, or `infrastructure/azure/` without explicit instruction.
- New optional infrastructure (like the observability stack) must be additive — a separate compose file combined via `-f`, never merged into the required production compose file.
- Preserve the existing Compose project `name:`/network isolation convention (`docker-compose.prod.yml` is `chatbotweb-prod`, must never collide with local-dev `docker-compose.yml`).
- Keep new infra provider-neutral where possible (OpenTelemetry over vendor-specific telemetry) per the deployment philosophy in `CLAUDE.md`.
- Never touch CI/CD workflow files (`.github/workflows/*`) as a side effect of an unrelated deployment task.

## Validation

`docker compose -f <files> config --quiet` to validate syntax/merge before anything else. If a real environment file is needed for full validation (`env_file:` directives), create a throwaway one, validate, then delete it — never leave a fabricated secrets file in the repo.

## Reporting

Full Report always — deployment changes are high blast-radius by definition.

## Expected output

New/modified compose/config files, validated via `docker compose config`, with the exact validation command and its exit code included in the report.

## What NOT to modify

- `docker-compose.prod.yml`, `deployment/caddy/Caddyfile`, `deployment/backup/*.sh`, `infrastructure/azure/**` without explicit instruction.
- Anything that would require an actual `docker compose up` against production or a real cloud account — this template covers config authoring/validation, not live deployment execution.
