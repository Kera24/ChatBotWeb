# Production Readiness Gates

Every feature reaching a Production-type release (`docs/releases/production.md`) must satisfy every gate below. This is the concrete checklist Release Approval (`docs/workflows/engineering-lifecycle.md` stage 16) verifies against. Enterprise releases (`docs/releases/enterprise.md`) satisfy these plus their own additional gates; internal/alpha/beta releases satisfy a proportionally lighter subset as defined in their own `docs/releases/*.md` pages.

## Tests

Unit and integration tests pass for every touched area, at or above the prior passing count (`CLAUDE.md`'s "How to preserve existing behaviour"). Validation commands per `docs/validation-policy.md`'s decision table for the area(s) touched.

## Evaluation thresholds

Deterministic evaluation gate passes with **unchanged** thresholds (`docs/adr/0025-deterministic-evaluation-gates.md`). Required for any change touching retrieval, generation, prompts, or guardrails.

## Regression checks

No decrease in existing evaluation case pass rate; no decrease in existing test count; `docs/checklists/*.md` for the touched domain(s) completed.

## Guardrails

No guardrail layer (A-H) removed, weakened, or bypassed (`docs/checklists/guardrails-checklist.md`). Any new layer went through shadow-mode validation first.

## Observability

New pipeline stages/features are traceable via `/observability`; trace-recording stays fail-safe (no-op default); no unredacted secret/prompt/response content persisted (`docs/checklists/observability-checklist.md`).

## Documentation

Relevant `docs/architecture/*.md`/`docs/engineering/*.md` page updated if current-state behavior changed; new ADR written if this is a major architectural change (`docs/architecture/evolution-policy.md`).

## Rollback

A specific rollback plan is identified **before** deployment (`docs/sops/rollback.md`), not improvised after an issue is found.

## Performance

`docs/checklists/performance-checklist.md` completed — no unexplained p95 latency or cost regression.

## Security

`docs/checklists/security-checklist.md` completed — tenant isolation, RBAC, and redaction verified, not assumed.

## Deployment validation

`docs/checklists/deployment-checklist.md` completed; CI (`.github/workflows/verify.yml`) green; migration preflight clean if schema changed.

## Customer readiness

Any customer-visible behavior change is documented somewhere a support/success function could find it; any feature requiring tenant opt-in/configuration has that path tested, not just the underlying logic.

## Gate enforcement

Every gate above is a hard requirement for Production releases — none are informally overridden. A gate that can't be satisfied means the release isn't ready, not that the gate should be skipped for this one case (`CLAUDE.md`'s standing instruction on evaluation/guardrail integrity applies equally to every gate here).
