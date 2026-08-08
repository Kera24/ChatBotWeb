# Regression Release Policy

Related: [Production Feedback Loop](../04_Engineering/Evaluation_Production_Feedback_Loop.md), [Nightly Evaluation VPS Guide](./Nightly_Evaluation_VPS_Guide.md).

## What blocks a release

`app.evaluation.production_gate.evaluate_production_readiness()` — invoked via `npm run eval:release-gate-check`, wired as an optional step in `scripts/release-gate.mjs` — returns a `GateVerdict(passed, reasons)`. **All** of the following being false is required to pass:

1. **An approved production failure case still fails.** Any `EvaluationCandidate` with `triage_status == "accepted"` and a `promoted_case_id` set, whose case has no result in the latest completed run (incomplete evidence) or whose latest result is `passed=False`/`hard_failure=True`.
2. **A hard deterministic failure exists.** The latest completed run for the dataset has `hard_failure_cases > 0`.
3. **Isolation or citation regressed.** Isolation-category (`app.evaluation.categories.ISOLATION_CATEGORIES`) hard failures increased, or citation coverage dropped, versus the previous completed baseline run.
4. **Dataset version changed without a completed evaluation.** `EvaluationDataset.version` differs from the latest completed run's `dataset_version` snapshot — i.e. something was promoted since the dataset was last actually tested.
5. **The baseline is stale.** The latest completed run is older than `--max-baseline-age-days` (default 7).
6. **Required evaluation evidence is incomplete.** The dataset's version was bumped and no `EvaluationRegressionReport` has been produced since.

Graders (LLM-as-judge, `app.evaluation.graders/`) remain **advisory only** — nothing above reads `judge_scores_json`. This matches the pre-existing evaluation framework rule (`docs/architecture/evaluation.md`): graders inform review, they don't gate deployment.

## What does not block

- New candidates sitting in `new`/`triaged`/`needs_information` — an unreviewed queue is not itself a release blocker, only an *accepted-but-still-failing* case is.
- `rejected`/`duplicate` candidates — explicitly determined not to be real defects.
- The deterministic mock-mode `eval:launch` step already in `release-gate.mjs` — unchanged, still advisory, for the documented reason that the current retrieval pipeline has no similarity-confidence threshold (see that script's inline comment).

## Running it

```bash
npm run eval:release-gate-check -- --dataset <id> --assistant <id> --organisation <id> --workspace <id> --format json
```

Exit 0 pass, 1 fail (prints each blocking reason), 2 operational error (dataset not found). In `scripts/release-gate.mjs`, pass all four `--feedback-loop-organisation/-workspace/-assistant/-dataset` flags to enable this gate for a real deployment; without them it's skipped (advisory, not failed) since the generic release-gate script has no way to infer which assistant/dataset to check for a given deployment.

## Known limitation: SQLite timestamp precision

Condition 6 above compares `EvaluationRegressionReport.created_at >= EvaluationDatasetVersionEvent.created_at`. On Postgres (production) this is reliable (microsecond precision). On SQLite (local dev/tests), `CURRENT_TIMESTAMP` is second-resolution — a regression report created in the same wall-clock second as a version bump can occasionally compare unpredictably depending on rounding. This has been observed in manual local testing; it does not affect production (Postgres-backed) deployments and has not caused a flaky assertion in the automated test suite (no test creates both rows within the same demonstrated race window), but is worth knowing if a local dev script produces a surprising "missing evidence" result immediately after promoting and reporting in quick succession.

## Regression reports as evidence

`npm run eval:regression-report -- --run <candidate_run_id> --baseline-run <baseline_run_id>` produces the `EvaluationRegressionReport` row condition 6 above checks for. Run it after every full-dataset run (nightly/weekly) and after every focused run following a promotion — see the [Nightly Evaluation VPS Guide](./Nightly_Evaluation_VPS_Guide.md) for cadence.
