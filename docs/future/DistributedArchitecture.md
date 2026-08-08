# Distributed Architecture

## Purpose

Move from a single-VPS, single-instance deployment toward a horizontally distributed architecture (multiple API/web instances, load-balanced) for resilience and capacity beyond what one host provides.

## Current limitation

`docker-compose.prod.yml` runs one instance of each service on one VPS (`docs/adr/0027-vps-first-controlled-pilot-hosting.md`); there is no load balancing, no multi-instance failover, and rate limiting/session handling assume a bounded single-host deployment (though `RATE_LIMIT_REDIS_PREFIX`/distributed rate limiting was already designed with this in mind — ADR 0009).

## Why postponed

Single-instance deployment is correctly sized for controlled-pilot scale; distributing before there's a capacity or availability need adds operational complexity (service discovery, distributed session/rate-limit consistency, multi-instance migration coordination) with no current benefit.

## Dependencies

- `docs/engineering/scaling-strategy.md`'s higher customer tiers as the trigger.
- ADR 0009's distributed rate-limiting policy (already designed for this, currently "Proposed" status — would need to move to "Accepted" and be verified under real multi-instance load).
- `docs/future/DeploymentRoadmap.md`'s intermediate "split services across more than one VPS" step likely precedes full distribution.

## Implementation phases

1. Externalize any remaining in-process state (verify nothing besides the already-external Postgres/Redis holds request-scoped state that wouldn't survive a second instance).
2. Add a load balancer in front of multiple API/web instances (Caddy can do this, or a dedicated LB).
3. Verify distributed rate limiting (ADR 0009) and session handling work correctly under real multi-instance traffic.
4. Coordinate the one-shot `migrate` job to run exactly once even with multiple instances starting concurrently (already a single job in Compose; must remain single under any orchestrator).

## Technical design

No RAG-pipeline or business-logic change — this is purely infrastructure/deployment topology. The `RAGOrchestrator`/guardrail/evaluation code is already stateless per-request and doesn't need to change.

## Evaluation plan

Load testing under realistic multi-instance traffic; verify no request-affinity assumptions were silently baked into the single-instance deployment (e.g. in-memory rate limit fallback, `RATE_LIMIT_LOCAL_FALLBACK_ENABLED`, must not silently diverge between instances).

## Rollback strategy

Revert to single-instance Compose deployment; since no application-layer state changes are introduced, rollback is purely an infrastructure topology change.

## Success metrics

Demonstrated capacity/availability improvement (higher sustained throughput, survives single-instance failure) with no correctness regression in rate limiting or session handling.
