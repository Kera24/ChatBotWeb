# Prompt Evaluation and Promotion Policy

See `docs/architecture/evaluation.md` for the underlying evaluation framework this reuses, and `docs/architecture/prompts.md` for the composite-identity/rendering-bridge context. This document covers `app.evaluation.prompt_promotion_gate`, the evaluation-gated promotion check for one candidate `PromptVersion`.

## What it does

`evaluate_prompt_candidate()` mirrors `app.evaluation.production_gate`'s shape: given a candidate `PromptVersion.id`, it runs the **real** evaluation engine (`app.evaluation.engine.run_evaluation()`, never a reimplementation) against a caller-supplied dataset, with `EvaluationRunOptions.prompt_version_override_id` set to the candidate — this forces every case's `RAGOrchestrator.answer()` call to resolve that exact candidate for its layer (see the fail-open/fail-loud split in `docs/architecture/prompts.md`), while other layers resolve to whatever is currently deployed. It then compares the resulting run against the most recent **non-candidate** completed run for the same widget+dataset (i.e. "what's currently live," found by `_latest_baseline_run()` filtering for `prompt_version_id IS NULL`) using the **unmodified** `app.evaluation.gate.evaluate_gate()` — this module never touches `app.evaluation.policy`/`app.evaluation.gate`, only calls them.

## "Run the guardrail suite" is this same evaluation run

All 8 guardrail layers (A–H) execute unconditionally inside `RAGOrchestrator.answer()` for every case in the run — there is no separate parallel guardrail-only test runner. A guardrail regression introduced by a candidate prompt surfaces as a scoring/hard-failure difference in the same run this module already produces.

## Integrity check

After the run completes, `evaluate_prompt_candidate()` asserts `candidate_run.prompt_version_id == candidate_version_id`, raising `PromptGateIntegrityError` if they diverge. This is deliberately stricter than "did the gate pass" — a mismatch here means the evaluation run did not actually exercise the requested candidate (a bug, not a quality failure), and the gate must refuse to report a verdict at all rather than risk a false PASS. Note the distinction from "the candidate id doesn't exist": a bogus id still gets faithfully recorded as what was requested (every case fails to resolve it, `EvaluationRun.prompt_version_id` still equals the requested — nonexistent — id), which correctly surfaces as a **failing verdict**, not an integrity error — see `apps/api/tests/test_prompt_promotion_gate.py` for both cases exercised directly.

## What promotion does *not* do automatically

Running the gate never transitions the candidate's status by itself — approval remains a deliberate, separate action taken by an authorised reviewer through the API/dashboard (`POST .../versions/{id}/transition`), matching this codebase's existing "no automatic-promotion path" rule for evaluation candidates. `deploy_version()` requires `status == "approved"` but does not itself re-run or re-check the gate.

## CLI

`python -m app.operations.prompt_promote --candidate-version <id> --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--format text|json]` (npm script: `prompt:promote`) — wraps `evaluate_prompt_candidate()` for CI/CD or terminal use, mirroring `eval_release_gate_check.py`'s exit-code convention: `0` pass, `1` fail (blocking), `2` operational error (dataset not found, or `PromptGateIntegrityError`). It only reports; like the API, it never transitions status.

## No hidden safety-threshold changes

This module never modifies `app.evaluation.policy.DEFAULT_POLICY` or `app.evaluation.gate.evaluate_gate()`'s logic — a candidate prompt is held to exactly the same launch-readiness bar as everything else evaluated through this framework.
