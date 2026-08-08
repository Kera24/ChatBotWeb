# Continuous Improvement Loop

The permanent engineering loop every production issue and every piece of usage data eventually feeds into. This is the operational expression of `docs/principles/engineering-principles.md`'s evidence-based-decisions principle, and the concrete mechanism behind `docs/workflows/engineering-lifecycle.md`'s final three stages (Production Feedback, Golden Dataset Update, Continuous Improvement).

```
Customer Usage → Telemetry → Observability → Failures → Incident Analysis
  → Golden Dataset → Evaluation → Architecture Review → Implementation
  → Deployment → Customer Usage (loops)
```

## Customer Usage

Real tenant traffic through the widget/dashboard is the ultimate source of truth — every improvement traces back to something a real user did or experienced.

## Telemetry

Every request is captured per `docs/operations/observability-workflow.md`'s trace model — this is what makes usage analyzable rather than anecdotal.

## Observability

Dashboards and alerts (`/observability`) surface aggregate patterns; individual traces surface specific incidents.

## Failures

Not every production event needs this loop — only genuine failures (guardrail blocks, fallbacks, evidence-insufficient responses, latency/cost anomalies, customer-reported bugs) enter it. Successful requests confirm the system is working; they don't by themselves drive change.

## Incident Analysis

Root-cause each failure category via the matching `docs/runbooks/*.md`/`docs/sops/*.md`. The goal of this stage specifically is turning "something went wrong" into "here is the specific, fixable cause."

## Golden Dataset

Every root-caused failure that represents a real, recurring pattern becomes a new evaluation case — this is the step that makes the loop cumulative rather than one-off. A fix without a corresponding case is a patch; a fix with one is a permanent improvement to the platform's quality bar.

## Evaluation

The updated case set becomes the new baseline every future change is measured against — this is why `docs/adr/0021-evaluation-before-guardrails.md`'s evaluation-first ordering matters structurally, not just historically: the case set has to exist and grow for this loop to function at all.

## Architecture Review

If the failure pattern reveals something the architecture itself should handle differently (not just a point fix), it goes through `docs/architecture/evolution-policy.md`'s review process — possibly resulting in a new ADR or a `docs/future/*.md` spec.

## Implementation

The fix (point fix or architectural change) is built following `docs/workflows/engineering-lifecycle.md` or `docs/workflows/ai-development.md`, as appropriate.

## Deployment

Ships through the normal release process (`docs/releases/`), with the specific evaluation case added in Golden Dataset now part of the permanent regression suite.

## Customer Usage (loop closes)

The fix is now live; the next round of real usage either confirms the fix worked (no recurrence) or reveals it was incomplete (recurrence, re-entering the loop with more information than before).

## Why every production issue eventually improves Conversa

Because Golden Dataset Update is a mandatory stage, not an optional one, no failure pattern is fixed only once in production without also becoming a permanent, automatically-checked guarantee. This is what distinguishes Conversa's engineering model from ad hoc firefighting: incidents don't just get resolved, they get converted into evaluation coverage that prevents silent regression later. Over time, this means the evaluation case set is not a fixed artifact from launch — it is a continuously growing record of every real failure mode the platform has ever encountered and fixed, which is precisely what makes `docs/principles/engineering-principles.md`'s "no regression acceptance" principle enforceable rather than aspirational.
