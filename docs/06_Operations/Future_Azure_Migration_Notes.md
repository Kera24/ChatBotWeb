# Future Azure Migration Notes

The previous Azure environment was deleted for cost reasons; this launch
targets a single low-cost VPS instead (see [VPS_Deployment_Guide.md](./VPS_Deployment_Guide.md)).
**All Azure infrastructure-as-code and runbooks remain intact and untouched
by this work** - they are the documented future-scale target, not dead code.

## What's preserved, and where

| Location | Purpose |
|---|---|
| `infrastructure/azure/main.bicep` + `infrastructure/azure/modules/*.bicep` | Full IaC: Container Apps, Postgres, Redis, Front Door/CDN, Key Vault, Container Registry, monitoring/alerts, storage |
| `infrastructure/azure/environments/*.bicepparam` | Staging/pilot environment parameter sets |
| `docs/06_Operations/Azure_*.md` (10 runbooks) | Infrastructure deployment, app deployment, migrations, monitoring/alerting, GitHub OIDC bootstrap, secret bootstrap, staging validation/rollback drill, widget domain/TLS, production pilot enablement |
| `scripts/azure-*.mjs` | Deploy, migrate, smoke-test, rollback, staging-validate, telemetry/alert validation, pilot-readiness gate |
| `apps/api/app/operations/telemetry.py` | Azure Monitor OpenTelemetry integration - no-ops gracefully today (gated by `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=false`) |

Nothing in this launch-readiness pass removed, weakened, or renamed any of
the above. The VPS and Azure deployment targets share the same application
code, the same `Settings` dataclass (`app/core/config.py`), and the same
Alembic migrations - only the deployment *wrapper* differs
(`docker-compose.prod.yml` + Caddy vs. Bicep + Container Apps + Front Door).

## What would change when moving from VPS to Azure

1. **Reverse proxy / TLS** - `deployment/caddy/Caddyfile` is replaced by Azure Front Door (`infrastructure/azure/modules/front-door.bicep`), which already has the widget static-asset routing rules (`widgetDeliveryRules`) mirroring what the Caddyfile does for `/widget-sdk/*`, `/embed/index.html`, `/assets/*`.
2. **Database/Redis** - `postgres`/`redis` containers are replaced by Azure Database for PostgreSQL (`modules/postgres.bicep`) and Azure Cache for Redis (`modules/redis.bicep`); `DATABASE_URL`/`REDIS_URL` point at managed endpoints instead of container DNS names.
3. **Document storage** - `LOCAL_UPLOAD_ROOT`'s local-filesystem storage (`app/services/local_storage.py`) has no Azure Blob equivalent implemented yet; migrating uploads off local disk to Blob Storage (`modules/storage.bicep` already provisions a storage account, currently only used for widget static assets) is a real code change, not just a config swap - budget for it before scaling past what a single VPS's local disk comfortably holds.
4. **Widget static assets** - `deployment/widget/Dockerfile`'s output (matching `npm run widget:release:build`'s layout) is exactly what already gets published to Azure Blob Storage + Front Door in `scripts/publish-azure-widget-release.mjs` - no format change needed, only the publish target.
5. **Migrations** - `apps/api/app/operations/database_migration.py` is deployment-target-agnostic already; Azure runs it via `modules/migration-job.bicep` (a Container Apps Job) instead of the VPS's one-shot `migrate` Compose service. Same command, different runner.
6. **Telemetry** - flip `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=true` and set `APPLICATIONINSIGHTS_CONNECTION_STRING`; the instrumentation is already wired (`app/operations/telemetry.py`), just inert without those two variables.
7. **Release gate** - `scripts/validate-production-pilot-readiness.mjs` is the Azure-specific equivalent of this launch's `scripts/release-gate.mjs`; both ultimately exist to block a bad deploy, just with different evidence sources (Azure staging validation artifacts vs. direct local test/eval runs).

## What does *not* need to change

The application layer - FastAPI routes, RAG orchestration, guardrails,
evaluation framework, billing integration, and the Next.js app - is entirely
deployment-target-agnostic. Nothing in this VPS launch pass introduced a
VPS-only code dependency; moving to Azure later is an infrastructure/ops
migration, not an application rewrite.
