# Evaluation Checklist

## Required validation

- `npm run eval:test` and `npm run api:test`.
- A full evaluation run against the current case set, not just the new/changed cases.

## Things to verify

- `app.evaluation.policy`/`gate` thresholds are unchanged unless explicitly instructed (`CLAUDE.md`).
- New cases target a real, specific failure mode (not a synthetic one invented to pad coverage).
- Deterministic scoring (`evaluation/scoring.py`) remains the launch-gating signal; model-based grader dimensions (`docs/engineering/graders.md`) remain advisory unless a promotion decision was explicitly made and ADR'd.
- `GraderResultCache` cache-key inputs (dimension, context, rubric_version, grader_model) are unaffected by unrelated changes, so cache hits stay valid.

## Common mistakes

- Loosening a threshold to make a specific PR's evaluation pass.
- Treating a model-based grader dimension as gating without a calibration-backed promotion decision.
- Adding cases that don't correspond to any real observed or plausible failure.

## Required documentation

- Update `docs/architecture/evaluation.md`/`docs/engineering/evaluation.md` if the framework's shape changes.
- Any threshold change gets its own ADR (`docs/architecture/evolution-policy.md`).

## Definition of Done

Evaluation gate passes with unchanged thresholds; new cases are traceable to a real failure mode; grader/deterministic score separation is preserved.
