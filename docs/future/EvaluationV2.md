# Evaluation V2

## Purpose

Promote calibrated model-based grader dimensions from advisory to gating, and extend evaluation to run continuously against production traffic samples rather than only pre-release datasets.

## Current limitation

`docs/engineering/evaluation.md`/`docs/engineering/graders.md` — all rubric grader dimensions are advisory-only (`gating=False`) regardless of calibration status; evaluation runs are dataset-driven, not continuous against live traffic.

## Why postponed

`docs/adr/0025-deterministic-evaluation-gates.md` — promoting a dimension to gating requires sustained calibration evidence (≥ 0.8 agreement across multiple runs), which takes real time and repeated releases to accumulate; continuous production evaluation needs the observability trace pipeline (`docs/architecture/observability.md`) to be the data source, which had to exist first.

## Dependencies

- Sustained calibration agreement (`graders/calibration.py`) across multiple releases for any dimension being considered for promotion.
- Production AI trace data (`docs/architecture/observability.md`) as the sample source for continuous evaluation.

## Implementation phases

1. Track calibration agreement trend per grader dimension release-over-release (not just a single run).
2. Define and document explicit promotion criteria (this ADR-worthy decision happens per-dimension, not in bulk) — each promotion gets its own ADR, per `docs/adr/0028-engineering-documentation-as-a-first-class-deliverable.md`.
3. Continuous evaluation: sample production traces (redacted per `docs/architecture/observability.md`'s retention policy) into a rolling evaluation case set, run on a schedule.
4. Feed continuous-evaluation results into the same alerting/anomaly system observability already has (`docs/architecture/observability.md`'s deterministic drift signals), so evaluation regressions surface the same way operational anomalies do.

## Technical design

Continuous evaluation reuses the existing `EvaluationDataset`/`EvaluationCase`/`EvaluationRun`/`EvaluationResult` model — production-sampled cases are just another case source, not a new data model.

## Evaluation plan

This is itself an evaluation-infrastructure change, so it's validated by: (a) promoted dimensions correlating with human-reviewed quality judgments, and (b) continuous evaluation catching real regressions in a controlled test (inject a known-bad prompt version, verify it's flagged).

## Rollback strategy

Promoting a dimension to gating is reversible (revert to advisory) if it produces false positives in production; continuous evaluation can be paused without affecting the existing pre-release dataset-driven evaluation, which remains the primary gate throughout.

## Success metrics

At least one grader dimension promoted to gating with sustained low false-positive/false-negative rate; continuous evaluation catching at least one real production regression before it was reported by other means.
