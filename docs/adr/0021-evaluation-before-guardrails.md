# ADR-0021: Evaluation Before Guardrails (Sequencing)

Status: Accepted
Date: 2026-08-07

## Context

Both an evaluation framework (`docs/architecture/evaluation.md`) and a guardrail layer (`docs/architecture/guardrails.md`) were needed for a trustworthy RAG platform. They could have been built in either order, or in parallel. The team had to decide which comes first.

## Decision

Build and stabilize the evaluation framework (Dataset → Case → Run → Result, deterministic scoring, launch-gating policy/gate thresholds) before building guardrail layers A-H.

## Alternatives

- **Guardrails first** — rejected: without a way to measure whether a guardrail actually improves answer quality/safety (vs. just changing behavior), guardrail design decisions would be unverifiable opinion, not evidence. This directly conflicts with `docs/principles/engineering-principles.md`'s evaluation-first and evidence-based-decisions principles.
- **Build both simultaneously** — rejected: guardrails need a stable evaluation harness to measure their own effect (did adding evidence-sufficiency checking reduce ungrounded answers, measured how?); building them in parallel risks guardrails being tuned against a moving evaluation target.

## Tradeoffs

- Gains: every guardrail added after evaluation existed could be measured for its actual effect on evaluation scores, not just reviewed by eye.
- Costs: the platform operated for a period without guardrail protection while evaluation was being built — acceptable only because that period was pre-launch/pre-real-traffic.

## Consequences

- New guardrail layers should be validated against the evaluation suite (does the case set need new cases to exercise the new layer?) as part of adding them, not as an afterthought.
- `docs/adr/0022-guardrails-before-graders.md` continues this same sequencing logic one layer further.

## Future reconsideration triggers

None expected — this is a completed sequencing decision about build order, not an ongoing architectural constraint. It would only be revisited if evaluation itself were being fundamentally replaced.
