# Feature Development Lifecycle

The lifecycle for a product feature (as opposed to an AI-subsystem change — see `docs/workflows/ai-development.md` — or the master engineering lifecycle — `docs/workflows/engineering-lifecycle.md`, of which this is the product-feature specialization).

```
Idea → Specification → Architecture → Implementation → Validation → Evaluation
  → Review → Deployment → Monitoring → Maintenance → Retirement
```

## Idea

Same as `docs/workflows/engineering-lifecycle.md` stage 1: check `docs/future/*.md` and `docs/roadmap/roadmap.md` first. A feature idea that duplicates an existing spec should extend that spec, not fork a parallel one.

## Specification

Write (or reuse) a spec following the nearest `.prompts/*.md` template for the feature's domain (frontend-ui, backend-api, billing, etc.). A feature spec should state: what changes, which files, which RBAC role gates it, what evaluation coverage it needs (if it touches the AI pipeline), and what validation commands apply (`docs/validation-policy.md`).

## Architecture

Check `docs/file-boundaries.md` for the feature's domain before writing code. Confirm the feature reuses existing patterns (`CLAUDE.md`'s "Core philosophy": additive over invasive). If the feature requires a new pattern (new state-management approach, new CSS methodology, new ORM pattern), that's an architecture-review-level decision requiring explicit sign-off, not a unilateral implementation choice.

## Implementation

Server Component page → typed `lib/api/*.ts` loader → dumb presentational component (frontend); router → repository function → RBAC dependency (backend) — see `CLAUDE.md`'s "Rules for frontend work" / "Rules for backend work". Small, correct, verified changes over large, unverified ones.

## Validation

Run the narrowest test suite covering the change while developing (`docs/validation-policy.md`); before calling the feature done, run the commands the decision table specifies for every area touched. Use the relevant `docs/checklists/*.md` (frontend-checklist, backend-checklist, etc.) as the concrete verification list.

## Evaluation

If the feature touches retrieval, generation, guardrails, or prompts, it goes through the AI-specific evaluation stages in `docs/workflows/ai-development.md` before proceeding — a "feature" that happens to touch the AI pipeline doesn't get a lighter-weight path than a pure AI-subsystem change would.

## Review

Human review against `CLAUDE.md`, `docs/file-boundaries.md`, and the applicable `docs/checklists/*.md`. Reviewer verifies reported validation actually ran (`docs/reporting-policy.md`'s standard: no claiming a test passed without running it in-session).

## Deployment

Follow `docs/sops/deploying.md`. Release type (internal/alpha/beta/production/enterprise) determines the exact approval and monitoring requirements — see `docs/releases/`.

## Monitoring

Post-deployment observation window via `docs/architecture/observability.md`'s dashboard/alerts, proportional to the feature's risk/blast radius. Any anomaly attributable to the feature triggers the relevant `docs/runbooks/*.md`.

## Maintenance

A shipped feature isn't "done" forever — it accrues: bug fixes (via the normal lifecycle, scoped small), evaluation case coverage as production reveals edge cases (`docs/operations/continuous-improvement.md`), and documentation updates when its behavior changes (`docs/architecture/*.md`/`docs/engineering/*.md` must stay current, per `docs/adr/0028-engineering-documentation-as-a-first-class-deliverable.md`).

## Retirement

A feature being removed or replaced follows its own small lifecycle: confirm no other feature depends on it (grep call sites, per `CLAUDE.md`'s "How to preserve existing behaviour"), deprecate before deleting where there's an external contract (API field, widget config) involved, update every doc that references it (`docs/file-boundaries.md`, `docs/architecture/*.md`, any `docs/adr/*.md` that assumed its existence), and remove its evaluation cases only if they no longer represent real usage. Billing, evaluation, guardrail, and auth features additionally require explicit instruction to retire, per `CLAUDE.md`'s "Things Claude must NEVER do."
