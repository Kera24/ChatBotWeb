# ADR-0022: Guardrails Before Graders (Sequencing)

Status: Accepted
Date: 2026-08-07

## Context

`docs/engineering/graders.md` describes two grading strategies: deterministic/rule-based (launch-gating) and model-based LLM rubric grading (advisory, pending calibration). The rubric grader dimensions (relevance, groundedness, faithfulness, etc.) evaluate the *final* answer a user would see. Guardrail layers A-H (`docs/architecture/guardrails.md`) run inside the pipeline and can block, sanitize, or fall back before an answer is returned.

## Decision

Build and wire guardrail layers A-H into `RAGOrchestrator.answer()` before building the model-based grader system. Graders always grade the guardrail-passed answer, never a raw/pre-guardrail response.

## Alternatives

- **Graders first, guardrails after** — rejected: grading an answer that hasn't passed guardrails would mean scoring output the system would never actually return to a user (guardrail-blocked/fallback responses have a different, already-known-good shape — `answer_state="fallback"`). Grading pre-guardrail output measures a hypothetical the platform doesn't ship.
- **Grade both pre- and post-guardrail output** — rejected as unnecessary complexity for the pilot: doubles the grading surface for a comparison (guardrail effect) that evaluation-layer A/B analysis (`docs/adr/0021`) already covers more directly.

## Tradeoffs

- Gains: grader rubric scores are always meaningful — they describe what a real user actually received.
- Costs: grader dimensions can't yet be used to evaluate guardrail *decisions themselves* (e.g. "was this fallback the right call") as a matter of course; that would need a deliberately different grading target than what's built today.

## Consequences

- Any new grader dimension is applied to the post-guardrail, persisted `ChatMessage` content, not to intermediate pipeline state.
- If guardrail-decision-quality grading becomes a real need, it should be a distinct, explicitly named grading target, not folded into the existing answer-quality rubric — see `docs/future/GuardrailsV2.md` and `docs/future/EvaluationV2.md`.

## Future reconsideration triggers

A concrete need to evaluate guardrail-blocking decisions themselves (false-positive/false-negative rate on guardrail triggers), which would justify adding a second, guardrail-decision-focused grading target alongside the existing answer-quality one.
