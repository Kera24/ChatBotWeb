# ADR-0025: Deterministic Evaluation Gates

Status: Accepted
Date: 2026-08-07

## Context

`docs/engineering/graders.md` describes two grading strategies: deterministic/rule-based scoring and model-based (LLM rubric) grading. A launch-blocking gate (`app.evaluation.policy`/`gate`) needed a decision about which of these — or both — should be allowed to block a release.

## Decision

Only deterministic, rule-based evaluation results are launch-gating. Model-based (LLM rubric) grader dimensions are advisory-only until each dimension's calibration agreement (`graders/calibration.py`, threshold 0.8 against `fixtures/calibration_set.json`) has been demonstrated to hold, and remain advisory even then unless explicitly promoted.

## Alternatives

- **Gate on model-based grader scores from day one** — rejected: an LLM grader's own reliability is unverified until calibrated against a known-answer set; gating a release on an uncalibrated grader would mean the gate itself could be wrong in either direction (blocking good releases or passing bad ones) with no way to know which.
- **Never gate on model-based grading, keep it advisory forever** — rejected: closes off a real signal (rubric dimensions like groundedness/faithfulness) that deterministic rules can't easily capture; the calibration mechanism exists specifically to make eventual promotion possible.

## Tradeoffs

- Gains: the launch gate is deterministic and reproducible — the same case set always produces the same pass/fail, with no LLM-call variance in the blocking decision itself.
- Costs: real quality signals that only a rubric grader can catch (e.g. subtle unfaithfulness to the evidence) don't block a release today, only surface as advisory data.

## Consequences

- `app.evaluation.policy`/`gate` thresholds must never be changed to accommodate a specific PR — see `CLAUDE.md` and `docs/engineering/evaluation.md`'s explicit-instruction-required note.
- Promoting any grader dimension from advisory to gating is itself a decision that should get its own ADR when it happens, not a silent config change.

## Future reconsideration triggers

A grader dimension sustaining ≥ the calibration agreement threshold across multiple evaluation runs/releases, per `docs/future/EvaluationV2.md`'s promotion criteria.
