# Graders — Current / Future / Out of Scope

## Current

`apps/api/app/evaluation/graders/` holds two distinct grading strategies, run side by side:

- **Deterministic/rule-based** (`evaluation/scoring.py::score_case`, `graders/claims.py::extract_claims`/`deterministic_value_support`) — launch-gating; feeds `app.evaluation.policy`/`gate`.
- **Model-based (LLM rubric) grading** (`graders/engine.py`, `graders/rubrics.py`, `graders/provider.py`/`ollama_provider.py`, `graders/prompts.py`) — `GraderDimension` enum: relevance, groundedness, faithfulness, completeness, citation_support, clarity, directness, fallback_appropriateness, clarification_quality (`RUBRIC_VERSION = "v1"`). Currently **advisory only** (`gating=False` for every dimension) until calibration agreement clears the threshold.
- **Calibration**: `graders/calibration.py` runs rubric graders against `fixtures/calibration_set.json`, requires ≥ `_CALIBRATION_PASS_AGREEMENT_THRESHOLD` (0.8) agreement before a dimension could be promoted to gating.
- **Result caching**: `graders/cache.py::GraderResultCache` (see `docs/engineering/caching.md`) avoids re-grading identical combinations within a run.
- Kept in sync with `docs/04_Engineering/Grader_Rubrics.md`. Decision record: ADR 0022 (guardrails before graders, sequencing) — grading always runs against guardrail-passed answers, never bypassing guardrails to grade a raw/unfiltered response.

## Future

- Promoting individual calibrated dimensions from advisory to gating once calibration agreement holds across multiple releases — see `docs/future/EvaluationV2.md`.
- Additional rubric dimensions as new failure modes are observed in production (via observability traces, `docs/architecture/observability.md`).

## Out of scope (not planned)

- Using model-based grader output to auto-block a release without deterministic corroboration — model-based grading stays advisory-only until calibration explicitly justifies gating, never wholesale-trusted from day one.
