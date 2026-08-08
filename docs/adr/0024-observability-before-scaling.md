# ADR-0024: Observability Before Scaling

Status: Accepted
Date: 2026-08-07

## Context

The platform could have prioritized scaling work (connectors, hybrid retrieval, enterprise features) immediately after launch readiness, or prioritized AI observability (per-request tracing, cost accounting, quality/safety signals — `docs/architecture/observability.md`) first. Without observability, any scaling decision would be based on guesswork about what's actually slow, expensive, or failing in production.

## Decision

Build AI observability (trace model, redaction, cost accounting, quality/safety metrics, alerts, deterministic anomaly/drift signals) before undertaking scaling-oriented work (`docs/future/ScalingRoadmap.md`, `docs/future/HybridRetrieval.md`, etc.).

## Alternatives

- **Scale first, add observability later** — rejected: scaling decisions (which retrieval strategy, which provider, which infrastructure tier) made without production trace/cost/quality data are evidence-free, conflicting with `docs/principles/engineering-principles.md`'s evidence-based-decisions and production-first-mindset principles. Retrofitting observability after scaling also means the early scaling period is a blind spot with no trace history to diagnose it later.
- **Build a partial/ad hoc observability solution (logs only, no trace model)** — rejected: request-scoped correlation across the 14-stage pipeline (`docs/architecture/retrieval.md`) is exactly what plain logs can't give without a lot of manual correlation; the cost of the real trace model was judged worth paying once, up front.

## Tradeoffs

- Gains: every scaling decision made after this point has real trace/cost/quality data behind it; incidents in the observability period itself are diagnosable via the same system.
- Costs: delayed some scaling-oriented feature work; added five new database tables and a non-trivial instrumentation surface (14 pipeline stages) before any scaling problem was proven to exist.

## Consequences

- Future scaling proposals (`docs/future/ScalingRoadmap.md`, `docs/engineering/scaling-strategy.md`) should cite observability data (trace volume, latency percentiles, cost trends, guardrail trigger rates) as justification, not assumption.
- Observability itself must stay cheap enough not to become the next scaling bottleneck — the fail-safe no-op recorder pattern (`docs/architecture/observability.md`) exists partly for this reason.

## Future reconsideration triggers

If observability's own overhead (storage growth, write latency) becomes a measured scaling problem, its retention/aggregation design (`docs/future/ObservabilityV2.md`) should be revisited before scaling work elsewhere is blocked on it.
