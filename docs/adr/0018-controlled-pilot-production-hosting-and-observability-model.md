# ADR-0018: Controlled Pilot Production Hosting and Observability Model

Status: Accepted
Date: 2026-07-21

## Context

TASK-066 established repository-local widget production delivery, release artifacts, security headers, cache policy, synthetic real-backend verification, health checks, operational controls, rollback planning, and pilot readiness reporting.

TASK-067 established controlled-pilot-ready widget administration: immutable configuration revisions, draft/publish workflows, origin and public-key management, embed versioning, preview, publish/history/rollback, knowledge scoping, admin security hardening, accessibility-oriented checks, and an admin release gate.

The project now needs a concrete production pilot deployment model. The repository currently contains local Docker Compose, API/web Dockerfiles, widget release/header artifacts, and GitHub verification workflows. It does not contain committed cloud-provider infrastructure-as-code or a live deployment target.

Remaining provider-neutral would block controlled pilot execution. TASK-068A therefore selects the actual hosting and observability model, while still avoiding any production deployment or live infrastructure mutation.

## Decision

Use an Azure-first controlled pilot architecture.

The selected deployment model is:

- Azure Front Door Standard or Premium for public ingress, TLS, custom domains, CDN behavior, WAF/routing, and cache/header policy attachment.
- Azure Container Apps for the FastAPI API, authenticated Next.js web app, and optional worker/one-shot jobs.
- Azure Container Registry for immutable API/web/worker images.
- Azure Database for PostgreSQL Flexible Server with the `vector` extension for relational data and pgvector retrieval during pilot.
- Azure Blob Storage for private object/document storage.
- Azure Blob Storage plus Azure Front Door for widget SDK assets, SDK major aliases, iframe HTML, and hashed iframe assets.
- Azure Key Vault for production secrets.
- Azure Cache for Redis only when required by the deployed distributed rate limiter, queue, or worker implementation.
- Azure Monitor, Log Analytics, and Application Insights OpenTelemetry for privacy-preserving logs, metrics, traces, errors, dashboards, and alerts.
- GitHub Actions for CI/CD, release gates, manual production approval, migration jobs, release artifact publication, deployment, live browser smoke, and rollback planning.

The production pilot is a production-grade environment with controlled tenant/widget enablement, not a non-production pilot environment. GA remains blocked until controlled pilot deployment, observation, manual accessibility validation, security review, restore drills, rollback drills, support validation, and pilot feedback succeed.

## Production Domains

Final domains are placeholders until approved. The intended model is:

- `app.<domain>` for authenticated dashboard/admin web.
- `api.<domain>` for authenticated platform API.
- `widget-api.<domain>` for public widget API routes on the same FastAPI deployment with separate host/CORS policy.
- `widget.<domain>` for widget iframe HTML/static app.
- `cdn.<domain>` for SDK and immutable iframe assets.

All production domains terminate TLS at Azure Front Door with managed certificates. HSTS is enabled after domain validation.

## Release and Deployment Model

Release identity is composed of:

- Git SHA
- API image digest
- Web image digest
- SDK semantic version
- SDK major alias target
- Iframe static artifact manifest
- Checksums/SRI for immutable assets
- Widget pilot readiness report
- Admin readiness report

Production deployment requires manual approval after staging deployment and live smoke evidence. Migrations are executed by one controlled job, not by every API instance.

## Monitoring and Privacy

Azure Monitor and Application Insights collect operational evidence only.

Allowed operational signals include request IDs, route names, status categories, latency, safe error categories, release/environment, success/failure counts, readiness state, synthetic smoke state, and coarse widget/service identifiers where approved.

The monitoring model must not capture session tokens, Authorization headers, public message bodies, assistant answers, citation text, prompts, provider keys, database URLs, raw hostile origins, or browser replay containing conversations.

## Rollback Model

Rollback is artifact-specific:

- SDK rollback repoints the major alias to a previous immutable semantic version.
- Iframe rollback redeploys the previous static artifact manifest.
- API rollback deploys the previous container image revision.
- Web rollback deploys the previous container image revision.
- Database rollback is avoided as a routine mechanism; pilot migrations must be backward-compatible and forward-safe.

Post-rollback synthetic smoke is mandatory.

## Options Considered

### Option A - Azure-first

Azure provides a coherent pilot path for managed containers, PostgreSQL with pgvector, Key Vault, Blob Storage, Front Door, WAF, and Azure-native observability. It fits the repository's Docker-first model without introducing Kubernetes for pilot.

Selected.

### Option B - AWS-first

AWS could support the system with ECS/App Runner, RDS/Aurora PostgreSQL, S3, CloudFront, WAF, Secrets Manager, and CloudWatch. It is viable, but the project has no AWS-specific repository direction and would require assembling more service-specific decisions for the same pilot outcome.

Rejected for pilot.

### Option C - Cloudflare plus managed application/database provider

Cloudflare is strong for CDN, WAF, static delivery, and R2. However, FastAPI containers, PostgreSQL/pgvector, private network access, migrations, and backend workers would depend on an additional provider. This increases pilot integration complexity.

Rejected for pilot.

### Option D - Single VPS/container deployment

A VPS can run the existing Docker Compose style cheaply and simply. It is weaker for managed backups, secret management, TLS/CDN, monitoring, incident isolation, and rollback discipline. The pilot needs production-grade operational evidence.

Rejected for production pilot.

## Consequences

Positive consequences:

- The project now has a concrete production pilot target.
- PostgreSQL/pgvector remains the vector path for pilot.
- Widget static delivery maps directly to the B1 immutable/alias/cache/header model.
- Container Apps keeps deployment simpler than Kubernetes while preserving revisions and health probes.
- Azure Monitor/App Insights can implement B3 provider-neutral alert definitions with privacy constraints.
- GitHub Actions can remain the deployment orchestrator with manual approvals.

Negative consequences and risks:

- Azure Front Door, Container Apps, private networking, and header/cache rules require careful implementation in B tasks.
- Current API/web Dockerfiles use development commands and must be productionized before deployment.
- Exact cost requires current Azure pricing and approved region during implementation.
- If Redis-backed rate limiting or queueing is required, Azure Cache for Redis adds another managed service.
- A real staging deployment and rollback drill remain required before any customer pilot.

## Implementation Impact

TASK-068A does not implement infrastructure. It creates the plan for:

- TASK-068B1 - Azure infrastructure-as-code and hosting configuration
- TASK-068B2 - CI/CD deployment and rollback automation
- TASK-068B3 - Azure monitoring/error tracking/alerts/uptime integration
- TASK-068B4 - Staging deployment, live browser smoke, synthetic tenant isolation, rollback drill
- TASK-068B5 - Production pilot deployment, domain validation, customer enablement, manual accessibility/security gate

## References

- Azure Container Apps overview: https://learn.microsoft.com/en-us/azure/container-apps/overview
- Azure PostgreSQL Flexible Server pgvector: https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector
- Azure Blob static website hosting: https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-static-website-host
- Azure Storage custom domains with Azure Front Door: https://learn.microsoft.com/en-us/azure/storage/blobs/storage-custom-domain-name
- Azure Monitor OpenTelemetry/Application Insights: https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable
