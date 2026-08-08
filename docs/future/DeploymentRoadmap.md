# Deployment Roadmap

## Purpose

Define the path from the current single-VPS deployment toward the retained Azure architecture (or another target), and what intermediate steps exist between them.

## Current limitation

`docs/adr/0027-vps-first-controlled-pilot-hosting.md` — single VPS only; no horizontal scaling, no managed-service redundancy, no multi-region capability.

## Why postponed

The VPS deployment is deliberately sufficient for controlled-pilot scale; building toward Azure activation before there's a scale-driven reason would be premature spend (`docs/principles/engineering-principles.md`'s cost-aware-engineering principle).

## Dependencies

- `docs/adr/0029-retain-azure-architecture-without-deploying.md`'s retained IaC as the target architecture.
- `docs/engineering/scaling-strategy.md`'s tenant/traffic thresholds as the trigger.

## Implementation phases

1. Intermediate: vertical scaling of the existing VPS (larger instance) if load approaches capacity before a full migration is justified.
2. Intermediate: split services across more than one VPS (e.g. dedicated DB host) if a single-host bottleneck is identified, without yet moving to Azure.
3. Full migration: activate `infrastructure/azure/` per ADR 0018's original architecture once scale/compliance triggers are met.
4. Cutover executed with a dual-run/shadow period (both VPS and Azure serving traffic, gradually shifted) rather than a hard switch.

## Technical design

Migration target architecture is already designed (ADR 0018); this roadmap's job is sequencing the *trigger conditions* and *intermediate steps*, not redesigning the target.

## Evaluation plan

Each phase gated on the specific scaling evidence that justifies it (traffic/latency/cost data from observability), not a calendar date.

## Rollback strategy

Intermediate steps (vertical scaling, service splitting) are reversible infrastructure changes. Full Azure migration should be executed as a reversible dual-run cutover, matching the rollback discipline already defined in ADR 0018's release/rollback model.

## Success metrics

No unplanned downtime or capacity incident precedes each scaling step — i.e., scaling happens ahead of need, triggered by evidence, not after an outage.
