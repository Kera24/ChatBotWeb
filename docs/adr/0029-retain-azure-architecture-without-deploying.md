# ADR-0029: Retain Azure Architecture Without Deploying

Status: Accepted
Date: 2026-08-07

## Context

`docs/adr/0027-vps-first-controlled-pilot-hosting.md` moved the active deployment target from ADR 0018's Azure-first architecture to a single VPS. This left the question of what to do with the already-built `infrastructure/azure/` Bicep IaC, KQL query pack, and Azure Monitor Workbook template: delete it, freeze it as reference-only, or actively keep it compatible with the live codebase.

## Decision

Keep `infrastructure/azure/` in the repository and keep the application compatible with it, without provisioning or deploying it. Compatibility is maintained structurally through the OpenTelemetry-first instrumentation choice (`docs/architecture/observability.md`'s dual-path OTel design) rather than through active testing against a live Azure environment.

## Alternatives

- **Delete Azure IaC entirely** — rejected: it represents real, reviewed engineering work (ADR 0018's full architecture decision), and deleting it would mean starting from zero if/when scale justifies the migration `docs/adr/0027` explicitly names as a future trigger.
- **Actively deploy and maintain a live Azure environment alongside the VPS** — rejected: doubles operational surface area and cost for no current benefit; the VPS pilot doesn't need a warm standby at this scale, and `docs/principles/engineering-principles.md`'s cost-aware-engineering principle argues against paying for infrastructure not being used.

## Tradeoffs

- Gains: a documented, ready migration target exists if the VPS-first pivot needs to be reversed; no Azure spend while it's not needed; instrumentation choices made for observability (OTel) double as the compatibility mechanism, so no separate "Azure-readiness" maintenance track is needed.
- Costs: `infrastructure/azure/` can silently drift out of compatibility with the live application if changes elsewhere aren't checked against it (mitigated by `docs/architecture/deployment.md`'s "never modify without instruction" flag, which keeps changes to it deliberate) — but drift risk is real since it isn't exercised by CI beyond path-scoped validation (`azure-infra-whatif.yml`, `azure-validate.yml`).

## Consequences

- Any change to core request/response handling, auth, or data models should consider whether it silently breaks Azure-path compatibility, particularly around OpenTelemetry span/attribute shape (`docs/architecture/observability.md`).
- `infrastructure/azure/**`-scoped CI workflows stay in place specifically to catch drift in the IaC itself, even though they don't exercise a live deployment.

## Future reconsideration triggers

The same scaling triggers as `docs/adr/0027`: tenant/traffic/compliance thresholds in `docs/engineering/scaling-strategy.md` that would justify actually provisioning the retained Azure architecture.
