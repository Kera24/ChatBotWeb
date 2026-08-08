# Scaling Strategy

Current architecture and what changes at each customer-count tier. Every migration in this document is evidence-triggered (`docs/principles/engineering-principles.md`, principle 2) — the counts below are illustrative thresholds, not calendar commitments, and the real trigger is always measured data from `docs/architecture/observability.md`, not the count itself.

## Current architecture (controlled pilot, ~tens of tenants)

Single VPS, Docker Compose (`docker-compose.prod.yml`): Postgres+pgvector, Redis, one `api` instance, one `web` instance, Caddy as the sole edge/TLS terminator. No caching layer beyond the evaluation-scoped grader cache. No connectors (manual upload only). No live AI provider (mock only). Azure IaC retained but not deployed. See `docs/adr/0027-vps-first-controlled-pilot-hosting.md`.

## ~100 customers

**What changes**: likely nothing structural yet — a single well-sized VPS can plausibly serve this tier, assuming per-tenant usage stays in the "controlled pilot" range. The main risk at this tier is a live AI provider replacing the mock provider (real latency, real cost, real rate limits) rather than tenant-count pressure itself.
**What stays**: single-instance deployment, pgvector, manual ingestion.
**Migration triggers**: sustained p95 latency degradation, or Postgres/pgvector CPU/memory pressure visible in `docs/architecture/observability.md`'s traces.
**Cost implications**: primarily AI provider cost (once live), not infrastructure — infrastructure stays cheap at this tier.
**Risks**: none structural; the main risk is under-observing (shipping a live provider without enough observability/evaluation maturity to catch quality regressions).

## ~1,000 customers

**What changes**: vertical scaling of the VPS (larger instance) as a first response; if that's insufficient, splitting services across more than one host (e.g. dedicated DB host) per `docs/future/DeploymentRoadmap.md`'s intermediate step. Caching (`docs/future/CachingV2.md`) likely becomes justified by real redundant-work evidence at this tier. Rate limiting (already designed for distribution, ADR 0009) gets its first real test if any horizontal split happens.
**What stays**: pgvector (unless a specific bottleneck is measured — `docs/adr/0020-delay-qdrant-migration.md`'s trigger may not yet be met), the core RAG pipeline/guardrail/evaluation architecture unchanged.
**Migration triggers**: measured single-host capacity limits; measured redundant-computation cost (embedding/provider calls) justifying a cache.
**Cost implications**: infrastructure cost grows modestly (larger instance or a second host); AI provider cost grows roughly linearly with usage unless caching offsets it.
**Risks**: premature horizontal splitting before it's needed (violates progressive enhancement, principle 10) is a bigger risk than under-scaling at this tier — most single-VPS setups have significant headroom before 1,000 tenants actually requires splitting.

## ~10,000 customers

**What changes**: this is the tier where `docs/future/QdrantMigration.md` and `docs/future/DistributedArchitecture.md` (multi-instance API/web behind a load balancer) become plausibly justified, if their respective evidence triggers are met. Connector framework and continuous ingestion (`docs/future/ConnectorFramework.md`, `docs/future/ContinuousIngestion.md`) are likely worth having shipped by this tier if tenant demand supports it — larger tenants are more likely to want automated ingestion.
**What stays**: the RAG orchestrator's single-entry-point design (`docs/architecture/retrieval.md`) — scaling changes *how* it's deployed and *what* it queries, never forks its logic per tenant or channel.
**Migration triggers**: measured pgvector recall/latency degradation at real corpus sizes; measured single-instance throughput ceiling.
**Cost implications**: infrastructure cost grows materially (multiple instances, possibly a dedicated vector database); this is the tier where `docs/future/CostOptimisation.md` work most directly pays for itself.
**Risks**: migrating pgvector→Qdrant or single-instance→distributed without the vector-search/stateless-request abstractions having stayed honest (i.e., if shortcuts were taken earlier that leaked pgvector-specific or single-instance-specific assumptions into business logic) makes this tier's migrations much harder than planned.

## ~100,000 customers

**What changes**: this is the tier where Azure activation (`docs/adr/0029-retain-azure-architecture-without-deploying.md`, ADR 0018's original architecture) becomes the most plausible path — managed Postgres, Container Apps, Front Door/WAF, and Azure Monitor at this scale likely outperform a hand-operated VPS fleet on reliability and operational burden, even accounting for cost. Enterprise features (`docs/future/EnterpriseRoadmap.md`) are very likely required by tenants at this scale.
**What stays**: the core AI pipeline architecture, evaluation-first development process, and guardrail model — scale changes infrastructure and operational tooling, not the fundamental product architecture.
**Migration triggers**: sustained multi-region/compliance/reliability requirements that a self-managed VPS fleet can't reasonably meet; enterprise-tenant contractual requirements (SLAs, data residency) that Azure's managed services are built for.
**Cost implications**: this is the tier where managed-cloud cost premiums are most likely to be worth paying for the reliability/compliance they buy — the calculus that favored VPS at pilot scale (ADR 0027) plausibly reverses here.
**Risks**: waiting too long to start the Azure migration once triggers are met (migrations take real time; starting reactively during a capacity crisis is worse than starting proactively once evidence is clear).

## Cross-cutting notes

- **What never changes across tiers**: tenant isolation (RBAC + scoped queries), the guardrail-before-generation model, evaluation-gated releases, and redaction-by-default observability. These are architectural invariants, not scale-dependent choices.
- **What always changes with evidence, never with assumption**: every migration above is gated on `docs/architecture/observability.md` data, per `docs/principles/engineering-principles.md`'s evidence-based-decisions principle — this document describes plausible tiers, not a committed timeline.
- See `docs/future/ScalingRoadmap.md` for the roadmap-sequencing view of the same material, and `docs/roadmap/roadmap.md` for current phase status.
