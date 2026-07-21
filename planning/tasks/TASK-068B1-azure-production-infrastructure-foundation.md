# TASK-068B1 - Azure Production Infrastructure Foundation

Status: Implemented
Sprint: Sprint 3H - Controlled Production Pilot Deployment
Type: Infrastructure-as-code foundation and repository configuration

## Objective

Implement the Azure infrastructure-as-code and repository configuration foundation for staging and controlled-production-pilot environments.

This task prepares deployable Azure resources through code only. It does not deploy production infrastructure, change DNS, provision live resources, add production credentials, or create customer data.

## Source Material

Read before implementation:

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/12_Controlled_Pilot_Production_Deployment_and_Validation_Architecture.md`
- `implementation-pack/02_Architecture/10_Widget_Controlled_Pilot_Deployment_and_Operations_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0016-widget-deployment-versioning-and-release-model.md`
- `docs/adr/0018-controlled-pilot-production-hosting-and-observability-model.md`
- `planning/tasks/TASK-066B1-widget-production-delivery-security-versioning.md`
- `planning/tasks/TASK-066B3-widget-operational-controls-observability-pilot-enablement.md`
- `planning/tasks/TASK-068A-controlled-pilot-production-deployment-monitoring-architecture.md`
- `docs/04_Engineering/Widget_Production_Delivery_Security_and_Versioning.md`
- `docs/06_Operations/Widget_Deployment_Runbook.md`
- `docs/06_Operations/Widget_Operational_Runbook.md`
- `docs/06_Operations/Widget_Rollback_Runbook.md`
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Infrastructure Discovery

The repository previously contained:

- Docker Compose for local PostgreSQL/pgvector, Redis, API, and web
- API and web Dockerfiles using development startup commands
- provider-neutral widget release/header/alert metadata in `deployment/widget/`
- GitHub verification workflows but no deployment workflow
- no committed Terraform, Pulumi, Helm, Kubernetes, Azure, AWS, Cloudflare, nginx, Caddy, Traefik, Render, Railway, Fly, Vercel, or Netlify production configuration

Runtime findings:

- PostgreSQL/pgvector is the current vector path.
- pgvector extension creation is already migration-managed by Alembic revision `0002_enable_pgvector_extension`.
- Redis is a real public rate-limit dependency and is enabled in Azure parameters by default.
- Document storage currently uses a local storage service; Azure Blob Storage is provisioned as the production target, but application adapter work remains future implementation.
- No production worker entry point is committed, so worker Container App provisioning is parameterized and disabled by default.

## IaC Technology Choice

Bicep is used for TASK-068B1.

Rationale:

- ADR-0018 selects Azure.
- The repository had no existing Terraform or Pulumi convention.
- Bicep supports native Azure resources and ARM what-if.
- Initial controlled pilot avoids an external state backend.

Do not introduce another IaC system without a future ADR.

## Implemented Foundation

Created:

- `infrastructure/azure/main.bicep`
- `infrastructure/azure/modules/container-apps.bicep`
- `infrastructure/azure/modules/container-registry.bicep`
- `infrastructure/azure/modules/front-door.bicep`
- `infrastructure/azure/modules/key-vault.bicep`
- `infrastructure/azure/modules/monitoring.bicep`
- `infrastructure/azure/modules/postgres.bicep`
- `infrastructure/azure/modules/redis.bicep`
- `infrastructure/azure/modules/storage.bicep`
- `infrastructure/azure/environments/staging.bicepparam`
- `infrastructure/azure/environments/pilot.bicepparam`
- `scripts/validate-azure-infra.mjs`
- `scripts/azure-infra-whatif.mjs`

Updated:

- API Dockerfile for production startup without reload and non-root runtime user
- Web Dockerfile for production Next.js build/start and non-root runtime user
- Docker Compose to keep local dev/reload commands explicit
- GitHub Actions verify workflow with non-destructive Azure infra validation
- Manual Azure infrastructure what-if workflow skeleton

## Resource Model

Bicep defines:

- environment-scoped resource group
- Azure Container Registry
- Log Analytics and Application Insights foundation
- Key Vault
- PostgreSQL Flexible Server
- private document storage account/container
- widget static storage account/static website origin
- optional Azure Cache for Redis
- Azure Container Apps environment
- API Container App
- web Container App
- optional worker Container App placeholder
- manual migration Container Apps Job
- Azure Front Door Standard profile, endpoint, origins, routes, and cache/header rules

## Security Defaults

The foundation enforces or validates:

- ACR admin disabled
- ACR anonymous pull disabled
- Key Vault RBAC enabled
- Key Vault soft delete enabled
- pilot Key Vault purge protection enabled
- PostgreSQL public network access disabled
- PostgreSQL secure transport required
- Storage HTTPS only
- private document storage public blob access disabled
- no secrets in checked-in parameter files
- no database URL in browser/public parameter files
- API/web production Docker commands
- health probes for API liveness/readiness

## Known Gaps

B1 does not complete live Azure deployment. Remaining implementation work:

- final Azure subscription/resource validation
- private networking/private DNS validation
- role assignments for ACR pull, Key Vault, and Blob access
- GitHub OIDC bootstrap in Azure
- Front Door custom-domain validation and external DNS records
- real image digest deployment
- static widget artifact upload/publish automation
- monitoring alert rules/dashboards
- staging live browser smoke
- production pilot deployment

## Verification

Run:

```bash
npm run infra:azure:validate
npm run infra:azure:whatif -- staging
npm run verify
git diff --check
```

What-if is non-destructive and exits without deployment when Azure credentials or secure parameters are missing.

## Next Recommended Task

TASK-068B2 - Azure CI/CD Deployment Pipeline, Database Migrations, Release Promotion, and Rollback Automation
