# TASK-068A - Controlled Pilot Production Deployment, Domain Wiring, Monitoring, and Post-Deploy Validation Architecture

Status: Proposed
Sprint: Sprint 3H - Controlled Production Pilot Deployment
Type: Architecture and deployment planning only

## Scope

Define the concrete controlled-production-pilot deployment architecture for the platform and embeddable widget system. This task creates the production hosting, domain, monitoring, release, rollback, and validation plan that converts the repository-local readiness work from TASK-066 and TASK-067 into an executable deployment model.

This task does not deploy infrastructure, change DNS, provision cloud resources, add production credentials, modify live environments, or mutate production data.

## Source Material

This task is based on:

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/09_Embeddable_Widget_SDK_Architecture.md`
- `implementation-pack/02_Architecture/10_Widget_Controlled_Pilot_Deployment_and_Operations_Architecture.md`
- `implementation-pack/02_Architecture/11_Widget_Administration_Publishing_and_Embed_Management_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0016-widget-deployment-versioning-and-release-model.md`
- `docs/adr/0017-widget-publishing-configuration-and-embed-management-model.md`
- TASK-066A through TASK-066B3
- TASK-067A through TASK-067B5
- Existing deployment, Docker, environment, workflow, widget release, and operational policy files

## Infrastructure Discovery

The repository currently establishes a local Docker-first infrastructure model, not a committed cloud provider implementation.

Discovered infrastructure files:

- `docker-compose.yml`
- `apps/api/Dockerfile`
- `apps/web/Dockerfile`
- `infrastructure/README.md`
- `deployment/widget/headers.json`
- `deployment/widget/alerts.json`
- `deployment/widget/sdk-versions.json`
- `.env.example`
- `.github/workflows/verify.yml`

No committed Terraform, Pulumi, Helm, Kubernetes, Cloudflare, AWS, Azure, Render, Railway, Fly, Netlify, Vercel, nginx, Caddy, or Traefik production deployment configuration currently defines the live production target.

The local stack uses PostgreSQL with pgvector, Redis, FastAPI, Next.js, and Docker Compose. GitHub Actions currently run repository verification gates and upload widget/admin readiness reports, but do not deploy production.

## Architecture Decision

TASK-068A selects an Azure-first controlled pilot architecture:

- Azure Container Apps for the FastAPI API, authenticated web app, and optional worker jobs
- Azure Container Registry for API/web/worker images
- Azure Database for PostgreSQL Flexible Server with pgvector for relational and vector data during pilot
- Azure Blob Storage for private document/object storage
- Azure Blob Storage plus Azure Front Door for immutable SDK assets, SDK major aliases, iframe HTML, and hashed iframe assets
- Azure Front Door Standard or Premium for public ingress, custom domains, TLS, WAF/routing, cache/header policy attachment, and static asset acceleration
- Azure Cache for Redis only where distributed rate limiting, queueing, or existing runtime dependency requires it
- Azure Key Vault for production secrets
- Azure Monitor, Log Analytics, and Application Insights OpenTelemetry for privacy-preserving monitoring and error visibility
- GitHub Actions for CI/CD, manual approvals, release promotion, smoke verification, and rollback planning

This is a concrete deployment model. Provider-neutral production deployment remains rejected for TASK-068A because the project now needs an executable controlled-pilot plan.

## Pilot Assumptions

- Controlled pilot, not GA
- Small number of approved tenants and widgets
- Exact allowed origins only
- Limited initial traffic
- Manual production approval required
- No scale-to-zero for public API/widget paths unless latency is explicitly accepted
- Synthetic production smoke tenants are permitted; customer production data is not used for verification
- Monitoring, alerts, rollback, backups, and post-deploy smoke are mandatory before tenant enablement

## Acceptance Criteria

TASK-068A is complete when:

- A concrete production hosting model is selected
- Production topology, domains, DB/vector/storage, background work, secrets, monitoring, CI/CD, migrations, rollback, smoke, pilot onboarding, accessibility, and security gates are defined
- ADR-0018 records the hosting and observability decision
- Implementation is split into controlled TASK-068B tasks
- No production infrastructure is deployed

## Implementation Split

- TASK-068B1 - Azure production infrastructure-as-code, hosting configuration, domains, secrets, PostgreSQL, storage, CDN, and environment wiring
- TASK-068B2 - CI/CD deployment pipeline, migrations, release promotion, rollback automation, and artifact publication
- TASK-068B3 - Azure Monitor, Application Insights, alerting, uptime checks, dashboard, and privacy-preserving log integration
- TASK-068B4 - Staging deployment, live full-stack FastAPI browser smoke, synthetic tenant isolation, and rollback drill
- TASK-068B5 - Production pilot deployment, production domain validation, pilot customer enablement, manual accessibility/security checklist, and post-deploy observation

## Verification

Required for this architecture task:

```bash
git diff --check
```

No production deployment, DNS change, cloud provisioning, or credential change is allowed by this task.
