# Deployment Architecture

**Never modify `docker-compose.prod.yml`, `deployment/caddy/Caddyfile`, backup/restore scripts, or `infrastructure/azure/` without explicit instruction** — production-safety-critical, hard to reverse quickly. See `CLAUDE.md`.

## Current target: single VPS, Docker Compose

`docker-compose.prod.yml` — Postgres (pgvector image), Redis, a one-shot `migrate` job (Alembic to head before API starts), `api`, `web`, `widget-assets` (build-only, populates a shared volume), `caddy` (the only service publishing host ports 80/443). Explicit Compose project `name: chatbotweb-prod` so it never collides with the local-dev `docker-compose.yml`'s containers/volumes.

**ADR note**: `docs/adr/0018-controlled-pilot-production-hosting-and-observability-model.md` originally selected an Azure-first controlled-pilot architecture. The repository has since launched on a single VPS instead (this file). `docs/adr/0027-vps-first-controlled-pilot-hosting.md` records that pivot and formally supersedes 0018's hosting choice; 0018's privacy/observability-signal constraints still apply. See also `docs/adr/0029-retain-azure-architecture-without-deploying.md` for why `infrastructure/azure/` was kept rather than deleted.

## Optional: VPS observability stack

`docker-compose.observability.yml` — OTel Collector + Prometheus + Loki + Tempo + Grafana, additive only (combine with `-f docker-compose.prod.yml -f docker-compose.observability.yml`). Not required for launch. See `docs/06_Operations/Grafana_Prometheus_Loki_Tempo_VPS_Guide.md`.

## Dockerfiles

- **`apps/api/Dockerfile`** — single-stage `python:3.12-slim`, installs `requirements.txt`, non-root `appuser`, `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- **`apps/web/Dockerfile`** — two-stage (`node:20-alpine` build → fresh `node:20-alpine` runtime), non-root `nextjs` user, only ships built `.next`/`app`/`components`/`lib`/`node_modules` (pruned to prod deps) into the runtime image, `npm run start`.

## Caddy (edge/reverse proxy)

`deployment/caddy/Caddyfile` — domains via env vars (`WEB_DOMAIN`/`API_DOMAIN`/`WIDGET_DOMAIN`/`TLS_EMAIL`, no hardcoded domains), automatic Let's Encrypt TLS. Three site blocks: web → `web:3000`, API → `api:8000` (extended timeouts for AI generation), widget domain → serves static SDK/iframe assets directly with per-asset-type cache rules and a strict CSP on the iframe shell. Sets HSTS/`X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy`/`Permissions-Policy`, hides the `Server` header, JSON access logs to stdout, request-body size caps as an edge backstop.

## Backup / restore

`deployment/backup/backup.sh` — `pg_dump | gzip -9` to `$BACKUP_DIR/postgres/`, plus a tar of the `uploads_data` volume via a throwaway `alpine` container; retention via `find -mtime +N -delete` (default 14 days); warns on low disk. `deployment/backup/restore.sh` — requires explicit `--db`/`--uploads` paths and interactive confirmation (or `--yes`); terminates connections, drops/recreates the DB, replays the dump; wipes and restores the uploads volume. Recommends running `database_migration preflight` after a restore.

## Azure (kept live, not the active target)

`infrastructure/azure/` — Bicep IaC (`modules/monitoring.bicep`, `modules/monitoring-alerts.bicep`, etc.), KQL query pack, an Azure Monitor Workbook template. Kept compatible via the OpenTelemetry-first instrumentation choice (see `docs/02_Architecture/Azure_Monitor_Application_Insights_Mapping.md`) so a future migration doesn't require re-instrumenting the app, but Azure is not provisioned/deployed as part of the current controlled-pilot launch.

## CI/CD

`.github/workflows/verify.yml` is the main gate (PR + push to `main`), validating the active VPS launch target: `npm run verify` (the full chain — see `docs/validation-policy.md`), then `npm run vps:release:gate -- --skip-verified-suites --migration-check-env-file .env.production.example` (`scripts/release-gate.mjs` — validates `docker-compose.prod.yml`/`docker-compose.observability.yml` config shape and runs a real `alembic upgrade head` against ephemeral Postgres via the actual `migrate` Compose service, using only the checked-in example env file's placeholder values, never a real secret), then widget pilot/ops/admin-release verification scripts. `--skip-verified-suites` avoids re-running the suites `npm run verify` already covered (api/web tests, lint, build, the deterministic evaluation framework) in the same job. `scripts/release-gate.mjs` also runs standalone (unconditionally, without `--skip-verified-suites`) as a human operator's actual pre-deploy gate — see the script's own usage comment.

The five `azure-*.yml` workflows are either path-scoped to `infrastructure/azure/**`/`scripts/azure-*.mjs`/etc. (`azure-validate.yml`) or `workflow_dispatch`-only (manual staging deploy/promote/rollback/what-if) — Azure deployment is manually triggered, never automatic on push, and `verify.yml` no longer runs Azure validation unconditionally on every PR (previously did; removed so an unrelated VPS-path change doesn't pay an Azure-validation tax, and so Azure validation can't substitute for actually validating the active deployment target). **Do not modify CI/CD workflow files as part of an unrelated task.**
