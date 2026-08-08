# Scaling & Deployment Playbook

The infrastructure-stage view of Conversa's scaling path. This is a companion to `docs/engineering/scaling-strategy.md` (the customer-count-tier view — 100/1,000/10,000/100,000 customers) and `docs/future/ScalingRoadmap.md`/`docs/future/DeploymentRoadmap.md` (the roadmap-sequencing view) — read all three together; this document adds the infrastructure-stage granularity the other two don't spell out step-by-step. Every transition below is evidence-triggered, per `docs/principles/engineering-principles.md`'s progressive-enhancement and evidence-based-decisions principles — the stages are a plausible path, not a committed timeline.

```
Development → Local → Single VPS → Multiple VPS → Managed PostgreSQL
  → Qdrant → Azure → Enterprise → Multi-region → Global
```

## Development

- **Infrastructure**: individual developer machines, mock providers, SQLite fallback.
- **Expected customers**: none (pre-tenant).
- **Expected load**: none.
- **Migration triggers**: N/A — this is the starting state for all new work.
- **Cost**: developer time only.
- **Risks**: none beyond normal development risk.
- **Rollback**: N/A.

## Local

- **Infrastructure**: `docker-compose.yml` (local-dev), Postgres+pgvector container, matches production shape at small scale.
- **Expected customers**: none (integration testing, demos).
- **Expected load**: single-user, ad hoc.
- **Migration triggers**: readiness to demo/test against a production-shaped stack.
- **Cost**: none beyond local compute.
- **Risks**: local-prod parity drift if `docker-compose.yml` and `docker-compose.prod.yml` diverge unnoticed.
- **Rollback**: N/A — always available in parallel with every later stage.

## Single VPS (current production stage)

- **Infrastructure**: `docker-compose.prod.yml` — Postgres+pgvector, Redis, one `api`, one `web`, Caddy edge. See `docs/adr/0027-vps-first-controlled-pilot-hosting.md`.
- **Expected customers**: controlled pilot, tens of tenants (`docs/engineering/scaling-strategy.md`'s "current architecture" tier).
- **Expected load**: bounded by one host's capacity; comfortably sufficient at this tier per `docs/CONSTITUTION.md`'s scaling strategy.
- **Migration triggers**: sustained p95 latency degradation or single-host resource pressure visible in `docs/architecture/observability.md`.
- **Cost**: one VPS instance — the cheapest stage in this entire progression.
- **Risks**: single point of failure (host loss = full outage until `docs/runbooks/vps-recovery.md` completes); no managed-service safety net.
- **Rollback**: N/A as a "rollback" — this is the current baseline other stages build on or (if reversed) fall back to.

## Multiple VPS

- **Infrastructure**: services split across more than one host (e.g. dedicated DB host, or a second app host behind a load balancer) — `docs/future/DistributedArchitecture.md`.
- **Expected customers**: ~1,000-tier (`docs/engineering/scaling-strategy.md`).
- **Expected load**: beyond single-host capacity but not yet requiring managed cloud services.
- **Migration triggers**: measured single-host capacity limits.
- **Cost**: modest increase (a second/third VPS instance).
- **Risks**: distributed-state correctness (rate limiting, sessions) needs verification under real multi-instance load — ADR 0009's distributed rate-limiting policy was designed for this but not yet load-tested.
- **Rollback**: consolidate back onto a single host if the split proves unnecessary or premature.

## Managed PostgreSQL

- **Infrastructure**: move Postgres+pgvector to a managed service (e.g. Azure Database for PostgreSQL Flexible Server, as ADR 0018 originally specified) rather than a self-hosted container.
- **Expected customers**: ~1,000-10,000 tier, or earlier if backup/reliability requirements outpace self-managed Postgres's operational safety margin.
- **Expected load**: database-layer reliability/backup requirements exceed what `deployment/backup/`'s script-based approach comfortably covers.
- **Migration triggers**: a real backup/restore incident, or database-layer reliability requirements from a specific tenant.
- **Cost**: managed-service premium over self-hosted Postgres, offset by reduced operational burden.
- **Risks**: migration itself (data transfer, connection-string changes, potential brief downtime window) needs the same dual-run/verified-cutover discipline as any other migration in this document.
- **Rollback**: revert to self-hosted Postgres if the managed service doesn't deliver the expected reliability/cost tradeoff (rare, but the self-hosted path remains documented and available).

## Qdrant

- **Infrastructure**: dedicated vector database alongside (or eventually replacing) pgvector — `docs/future/QdrantMigration.md`, `docs/adr/0020-delay-qdrant-migration.md`.
- **Expected customers**: ~10,000-tier, only once pgvector's measured performance is the actual bottleneck.
- **Expected load**: corpus/query volume where ANN indexing quality materially matters.
- **Migration triggers**: measured pgvector recall/latency degradation — see ADR 0020's explicit trigger.
- **Cost**: a second stateful service to operate (or a managed Qdrant Cloud cost).
- **Risks**: dual-consistency between Postgres (documents) and Qdrant (vectors) during migration; `docs/future/QdrantMigration.md`'s dual-write/shadow-read plan exists specifically to manage this.
- **Rollback**: dual-write phase makes rollback trivial pre-cutover; post-decommission rollback requires re-embedding from source text.

## Azure

- **Infrastructure**: activation of the retained `infrastructure/azure/` architecture (Front Door, Container Apps, Key Vault, Azure Monitor) — `docs/adr/0018`, `docs/adr/0029-retain-azure-architecture-without-deploying.md`.
- **Expected customers**: ~100,000-tier, or earlier if compliance/reliability requirements demand it.
- **Expected load**: beyond what a self-managed VPS fleet can reasonably operate.
- **Migration triggers**: sustained multi-region/compliance/reliability requirements, or enterprise-tenant contractual needs.
- **Cost**: materially higher than VPS, offset by managed-service reliability/compliance value at this scale.
- **Risks**: this is the single largest infrastructure migration in the entire path — see `docs/runbooks/azure-migration.md` for the execution procedure and its dual-run cutover discipline.
- **Rollback**: dual-run cutover keeps VPS available as a fallback throughout; full rollback becomes progressively harder the longer Azure has been the primary target, so this decision should not be reversed casually once made.

## Enterprise

- **Infrastructure**: no new infrastructure primitive by itself — this stage layers enterprise-specific capabilities (SSO, compliance controls, dedicated support tooling) atop whichever infrastructure stage is active at the time. See `docs/future/EnterpriseRoadmap.md`.
- **Expected customers**: any tenant with enterprise-tier requirements, independent of overall platform scale.
- **Expected load**: not primarily a load question — a trust/compliance/feature-completeness question.
- **Migration triggers**: a concrete enterprise-tenant requirement (`docs/adr/0026`-style demand evidence).
- **Cost**: feature-build cost plus (if certification-driven) compliance-audit cost.
- **Risks**: building enterprise features speculatively ahead of demand — explicitly guarded against, see `docs/future/EnterpriseRoadmap.md`'s "why postponed."
- **Rollback**: per-feature, following each contributing spec's own rollback plan (`docs/future/EnterpriseSSO.md`, `docs/future/ComplianceRoadmap.md`).

## Multi-region

- **Infrastructure**: Azure (or equivalent) deployed across more than one region, with data-residency and latency-driven routing.
- **Expected customers**: global enterprise tenants with explicit data-residency or latency requirements.
- **Expected load**: geographically distributed traffic where single-region latency is unacceptable.
- **Migration triggers**: a specific tenant's data-residency/compliance requirement, or measured latency complaints from a specific geography.
- **Cost**: significant — multiplies infrastructure cost roughly by region count, plus cross-region data-consistency engineering.
- **Risks**: tenant data must not cross region boundaries incorrectly — this is a tenant-isolation-adjacent invariant at a new axis (geography, not just organisation/workspace) and needs its own explicit design, not an assumption that existing isolation logic covers it.
- **Rollback**: consolidate to the primary region if a specific multi-region deployment doesn't justify its cost/complexity.

## Global

- **Infrastructure**: the long-term end state implied by `docs/CONSTITUTION.md`'s long-term platform vision — full multi-region, multi-channel, provider-diverse deployment.
- **Expected customers**: platform-scale, broad geographic and channel diversity.
- **Expected load**: the upper bound this entire document's progression is designed to eventually reach.
- **Migration triggers**: not a single trigger — the cumulative result of every earlier stage's triggers being met over time.
- **Cost**: the highest-cost stage; by this point cost-aware engineering (`docs/principles/engineering-principles.md`) should be a mature, continuously-applied discipline, not a new concern.
- **Risks**: operational complexity at this scale is itself the primary risk — every invariant established in earlier stages (tenant isolation, evaluation-gated releases, guardrail integrity) must still hold, at scale, without exception.
- **Rollback**: not meaningfully reversible as a whole — individual regions/components remain independently rollback-able per their own stage's plan above.

## Cross-cutting rule

No stage is skipped by fiat — each is entered only when its migration trigger is actually met, per `docs/adr/0024-observability-before-scaling.md`. A tenant requirement that seems to demand jumping straight to a later stage (e.g. a single enterprise tenant wanting multi-region) is evaluated on its own merits against that stage's specific cost/risk, not treated as an excuse to skip the intermediate stages' own trigger discipline.
