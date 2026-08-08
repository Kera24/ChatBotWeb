# Enterprise Roadmap

## Purpose

Umbrella roadmap tying together the individually-specced enterprise-oriented features (SSO, compliance, scaling) into a single sequenced view of "what enterprise readiness requires."

## Current limitation

The platform today targets pilot-scale, self-serve-style tenants; no enterprise-specific features (SSO, compliance certification, dedicated SLAs) exist.

## Why postponed

Each contributing feature (`docs/future/EnterpriseSSO.md`, `docs/future/ComplianceRoadmap.md`, `docs/future/ScalingRoadmap.md`) is individually gated on real enterprise-tenant demand; this roadmap doesn't add a new dependency beyond theirs, it just sequences them together.

## Dependencies

- `docs/future/EnterpriseSSO.md`
- `docs/future/ComplianceRoadmap.md`
- `docs/future/ScalingRoadmap.md` (enterprise tenants typically also drive scale requirements)

## Implementation phases

1. First enterprise tenant requirement surfaces a concrete need (most commonly SSO or a specific compliance control) — build that specific item first, not the whole roadmap speculatively.
2. Compliance certification pursued once enterprise-tenant volume justifies the fixed cost of certification (`docs/future/ComplianceRoadmap.md`).
3. Scaling investment (`docs/future/ScalingRoadmap.md`) as enterprise tenant traffic/data volume grows.
4. Dedicated SLA/support tooling considered only once the above are in place and an enterprise tenant explicitly requires it.

## Technical design

No new technical design of its own — this document exists purely to sequence the referenced specs so "enterprise readiness" isn't treated as one monolithic project.

## Evaluation plan

Each phase evaluated per its own contributing spec; this roadmap's success is measured by whether features were built in response to real demand, not spec-ahead-of-demand.

## Rollback strategy

Deferred to each contributing feature's own rollback plan.

## Success metrics

Enterprise tenant acquisition/retention attributable to specific delivered features, tracked per feature rather than as one bundled "enterprise" launch.
