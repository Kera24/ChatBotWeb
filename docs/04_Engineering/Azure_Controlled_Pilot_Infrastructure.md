# Azure Controlled Pilot Infrastructure

## Purpose

TASK-068B1 implements the repository infrastructure foundation for the Azure-first controlled pilot selected by ADR-0018. It prepares Bicep modules, environment parameters, Docker runtime readiness, validation scripts, and operations runbooks.

No production infrastructure is deployed by this task.

## Topology

The infrastructure foundation defines:

- Environment-scoped resource group
- Azure Container Registry
- Azure Container Apps environment
- FastAPI API Container App
- Next.js authenticated web Container App
- Manual Container Apps migration job
- PostgreSQL Flexible Server
- pgvector migration readiness
- Private document Blob Storage
- Static widget/SDK Blob Storage origin
- Azure Front Door profile, endpoint, routes, and cache/header rules
- Key Vault
- Log Analytics and Application Insights foundation
- Optional Redis

## Bicep Structure

```text
infrastructure/azure/
  main.bicep
  modules/
    container-apps.bicep
    container-registry.bicep
    front-door.bicep
    key-vault.bicep
    monitoring.bicep
    postgres.bicep
    redis.bicep
    storage.bicep
  environments/
    staging.bicepparam
    pilot.bicepparam
```

`main.bicep` runs at subscription scope so it can create the environment resource group. Modules are deployed into that resource group.

## IaC Technology Choice

Bicep is the selected IaC technology for B1.

Rationale:

- ADR-0018 selects Azure.
- The repository has no existing Terraform/Pulumi state or convention.
- Bicep supports native Azure resource types and ARM what-if.
- Initial pilot avoids a state backend requirement.
- GitHub Actions can run validation and what-if without deploying on PRs.

Terraform or Pulumi should not be introduced in parallel unless a future architecture decision replaces this model.

## Environment Model

Two checked-in parameter files exist:

- `staging.bicepparam`
- `pilot.bicepparam`

Neither contains secrets. The pilot file intentionally contains `<approved-domain-required>` placeholders and is not deployable until the approved production domain is supplied through a reviewed change or deployment overlay.

Secure deployment parameters include `postgresAdministratorPassword`, supplied by Azure/GitHub secret at deployment time.

## Naming

Resource names follow:

```text
<namePrefix>-<environment>-<resource>
```

Examples:

- `yoranix-staging-rg`
- `yoranix-pilot-ca-api`
- `yoranix-pilot-afd`

Azure globally unique names such as storage accounts and ACR remove hyphens and include a deterministic suffix where needed.

## Resource Groups

B1 uses one Resource Group per environment. ACR is environment-scoped for the first pilot foundation to keep RBAC and teardown boundaries simple. A future shared ACR remains possible once release promotion automation is implemented.

## Azure Container Registry

The ACR module uses Standard tier and disables:

- admin user
- anonymous pull

Runtime and deployment access should use managed identity/RBAC. Images are deployed by digest in B2.

## Container Apps

API and web share one Container Apps environment per environment.

API:

- external ingress on port 8000
- `/health/live` liveness probe
- `/health/ready` readiness probe
- multiple revisions for rollback
- Key Vault secret references
- managed identity
- conservative pilot replica bounds

Web:

- external ingress on port 3000
- production Next.js start command
- API origin set to `https://api.<domain>`
- managed identity
- conservative pilot replica bounds

Worker:

- disabled by default
- no ingress if enabled later
- documented because current repository has ingestion utilities but no committed production worker entry point

Migration:

- one manual Container Apps Job using the API image
- runs `python -m alembic upgrade head`
- no public ingress
- not executed by every API replica

## PostgreSQL and pgvector

The PostgreSQL module defines Azure Database for PostgreSQL Flexible Server with:

- PostgreSQL 16
- public network access disabled
- TLS required
- automated backups
- storage autogrow
- conservative pilot SKU defaults

pgvector is already migration-managed by `apps/api/alembic/versions/0002_enable_pgvector_extension.py` through:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The extension is not created manually by API startup.

## Blob Storage

Two storage accounts are defined:

- private document storage for tenant documents
- static widget/SDK asset storage for Front Door origin

Private document storage disables anonymous blob access and shared key access. Application access should use managed identity where practical.

The widget static account enables static website hosting for SDK and iframe artifacts. Azure Front Door applies public cache/header behavior from the B1 widget delivery model.

## Redis

Redis is enabled by default in environment parameters because public widget rate limiting currently has a Redis-backed implementation and fail-closed behavior. If a future deployment proves Redis is not required, `enableRedis` can be set to false with documented application behavior.

## Front Door

The Front Door module creates a Standard Azure Front Door foundation with:

- web origin group
- API origin group
- widget static origin group
- HTTPS-only forwarding
- HTTP-to-HTTPS redirect rule
- immutable SDK/asset cache rule
- short SDK major alias cache rule
- iframe HTML no-cache rule

Custom domain validation is not automated in B1 because DNS approval and records live outside the repository. The intended hostnames are represented in parameters and outputs.

## Domains and TLS

Intended hosts:

- `app.<domain>`
- `api.<domain>`
- `widget-api.<domain>`
- `widget.<domain>`
- `cdn.<domain>`

Azure-managed Front Door certificates are preferred. HSTS must not be enabled until HTTPS and domain behavior are verified.

## Key Vault

Key Vault uses RBAC authorization, soft delete, and pilot purge protection. It stores references for:

- API database URL
- Redis URL
- rate-limit identity secret
- public session token hash secret
- message idempotency hash secret
- preview grant signing secret
- web auth secret
- AI provider keys
- storage credentials only if managed identity cannot be used

Bicep creates the vault but does not create secret values.

## Identities and RBAC

Container Apps use system-assigned managed identities. B2 must add or verify role assignments for:

- ACR pull
- Key Vault secret read
- Blob Storage data access

GitHub Actions should use OIDC, not long-lived service principal secrets. One-time federated identity bootstrap is documented in the secret bootstrap runbook.

## Network Model

The B1 foundation selects private PostgreSQL access as the production pilot target and does not broadly expose the database. Full VNet/private DNS implementation and Front Door private-origin hardening are left for B2/B4 where actual Azure environment validation can be run.

Residual B1 gaps:

- Container App direct FQDN restriction is not fully enforced yet.
- Front Door custom domain resources are not bound until DNS validation.
- Private endpoint wiring is not complete in this foundation.

Application-level tenant, origin, session, and rate-limit controls remain mandatory and are not replaced by infrastructure.

## Environment Configuration

API safe runtime values:

- `APP_ENV`
- `PHASE`
- `SERVICE_NAME`
- `VERSION`
- `API_V1_PREFIX`
- `PUBLIC_WIDGET_ASSET_BASE_URL`
- `PUBLIC_WIDGETS_ENABLED`
- `PUBLIC_WIDGET_MESSAGES_ENABLED`
- `PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED`

API secrets:

- `DATABASE_URL`
- `REDIS_URL`
- `RATE_LIMIT_IDENTITY_SECRET`
- `PUBLIC_SESSION_TOKEN_HASH_SECRET`
- `PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET`
- preview grant signing secret
- provider credentials

Web public values:

- `NEXT_PUBLIC_API_BASE_URL`

Widget/SDK public build values are supplied by the existing widget release build and remain origin-only.

## Docker Runtime Readiness

B1 updates Dockerfiles so Azure images run production commands:

- API Dockerfile runs `uvicorn` without `--reload` and uses a non-root user.
- Web Dockerfile builds Next.js and runs `npm run start` as a non-root user.
- Docker Compose explicitly overrides local services back to dev/reload commands for local development.

## Validation

Local validation:

```bash
npm run infra:azure:validate
```

Non-destructive Azure what-if when credentials are configured:

```bash
npm run infra:azure:whatif -- staging
npm run infra:azure:whatif -- pilot
```

Ordinary CI runs static validation only. Production deployment is not automated by B1.

## Known Gaps for TASK-068B2+

- ACR pull and Key Vault role assignments must be completed against real identities.
- Front Door custom domain resources and validation records must be wired after DNS approval.
- Private networking/private DNS must be validated in Azure.
- Deployment image digests must replace bootstrap placeholders.
- Static widget artifact upload/publish automation belongs to B2.
- Monitoring alert rules and dashboards belong to B3.
- Staging deployment and live browser smoke belong to B4.
- Production pilot deployment and customer enablement belong to B5.
