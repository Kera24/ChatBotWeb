# Evaluation — Current / Future / Out of Scope

## Current

Dataset → Case → Run → Result framework, deterministic rule-based scoring is launch-gating, LLM rubric-based grading is advisory-only pending calibration. Full detail: `docs/architecture/evaluation.md`, `docs/engineering/graders.md`. Decision record: ADR 0021 (evaluation before guardrails), ADR 0025 (deterministic evaluation gates).

## Future

- Promoting calibrated grader dimensions from advisory to gating once calibration agreement holds ≥ target threshold across releases — see `docs/future/EvaluationV2.md`.
- Continuous/scheduled evaluation runs against production traffic samples, not just pre-release datasets — see `docs/roadmap/roadmap.md`.

## Out of scope (not planned)

- Loosening `app.evaluation.policy`/`gate` thresholds to make a feature pass — thresholds change only via explicit, reviewed instruction, never to unblock a specific PR.

**Requires explicit instruction to modify thresholds** — see `CLAUDE.md`.
