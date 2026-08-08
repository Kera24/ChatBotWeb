# ADR-0027: VPS-First Controlled Pilot Hosting (Supersedes ADR 0018's Hosting Choice)

Status: Accepted
Date: 2026-08-07
Supersedes: `docs/adr/0018-controlled-pilot-production-hosting-and-observability-model.md` (hosting/deployment-target decision only; 0018's privacy/observability-signal constraints remain in force)

## Context

ADR 0018 selected an Azure-first controlled-pilot architecture (Front Door, Container Apps, managed Postgres, Key Vault, Azure Monitor). Between that decision and the platform's actual launch, the repository shipped a single-VPS, Docker Compose-based production deployment instead (`docker-compose.prod.yml`, `deployment/caddy/Caddyfile`, `deployment/backup/`) — see `docs/architecture/deployment.md`. This ADR records that pivot explicitly, since it was not previously captured as a formal decision and left ADR 0018 and the actual repository state pointing in different directions.

## Decision

Launch and run the controlled pilot on a single VPS with Docker Compose (Postgres+pgvector, Redis, `api`, `web`, `caddy` as the sole port-publishing edge service), not on the Azure architecture ADR 0018 selected. Azure infrastructure-as-code is retained but not deployed (`docs/adr/0029-retain-azure-architecture-without-deploying.md`).

## Alternatives

- **Proceed with ADR 0018's Azure-first plan** — this was the original decision; superseded because a single VPS reaches controlled-pilot launch materially faster and cheaper, and the pilot's actual scale (a small number of tenants) does not yet require Azure Container Apps/Front Door-level infrastructure. ADR 0018 itself acknowledged Option D (single VPS) was "Rejected for production pilot" at the time — this ADR reverses that specific call in light of the launch-speed and cost priorities that ended up dominating.
- **Multi-VPS / self-managed Kubernetes** — rejected: adds orchestration complexity disproportionate to pilot scale; Docker Compose on one VPS is operable by a small team and matches the project's Docker-first local-dev model already in place.

## Tradeoffs

- Gains: fast, low-cost path to a real production pilot; one Compose file most contributors can already read end-to-end; Caddy gives automatic TLS without a separate CDN/WAF service.
- Costs: weaker managed backup/secret-management/incident-isolation posture than the Azure plan (ADR 0018 called this out directly about Option D); no built-in multi-region failover; scaling beyond one VPS's capacity requires a real migration, not just adding instances.

## Consequences

- `infrastructure/azure/` must be kept functional/compatible (OpenTelemetry-first instrumentation, per `docs/adr/0029`) even though it is not the active target, so a future migration doesn't require re-instrumenting the app.
- Backup/restore (`deployment/backup/`) and rollback runbooks (`docs/06_Operations/`) are the VPS pilot's substitute for Azure's managed equivalents, and must be kept drilled/tested since there is no managed-service safety net behind them.
- `docs/architecture/deployment.md`'s explicit "never modify without instruction" list (docker-compose.prod.yml, Caddyfile, backup/restore scripts, infrastructure/azure/) applies regardless of which target is active.

## Future reconsideration triggers

Tenant count, traffic, or compliance requirements crossing the thresholds in `docs/engineering/scaling-strategy.md` and `docs/future/ScalingRoadmap.md` — at which point ADR 0018's Azure architecture (already designed, not discarded) becomes the documented migration target rather than a from-scratch decision.
