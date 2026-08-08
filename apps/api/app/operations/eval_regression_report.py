"""CLI: compare a completed evaluation run against a baseline run and persist
a structured regression report (spec section 8).

    python -m app.operations.eval_regression_report --run <run_id> --baseline-run <run_id> --organisation <id> --workspace <id> [--created-by <label>]

Classifies cases present in the candidate run's results relative to the
baseline: new (no baseline result - typically a freshly promoted production
case), fixed (baseline failed, candidate passed), newly-failing (baseline
passed, candidate failed), still-failing (both failed). Reuses
app.evaluation.gate.evaluate_gate's existing baseline-comparison support for
the overall pass/fail verdict (pass-rate regression tolerance, hard-failure
increase) rather than reimplementing threshold logic.

Writes one EvaluationRegressionReport row (so the dashboard's Regression
Reports section can list it) and prints the same report as JSON for cron log
capture.

Exits 0 regardless of the verdict (use --gate to also fail the process on a
non-passing verdict, matching eval_report.py's convention), 2 on an
operational error.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_candidate_repository, evaluation_repository


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare an evaluation run against a baseline run and persist a regression report.")
    parser.add_argument("--run", required=True, help="Candidate (just-completed) evaluation run id.")
    parser.add_argument("--baseline-run", required=True, help="Baseline evaluation run id to compare against.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--created-by", default="system:manual", help="Label recorded as the report's creator (e.g. system:nightly, system:weekly).")
    parser.add_argument("--gate", action="store_true", help="Exit 1 if the verdict does not pass (in addition to the always-printed report).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    with SessionLocal() as db:
        candidate_run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.run)
        if candidate_run is None:
            print(f"Run {args.run} not found for that organisation/workspace.", file=sys.stderr)
            return 2
        baseline_run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.baseline_run)
        if baseline_run is None:
            print(f"Baseline run {args.baseline_run} not found for that organisation/workspace.", file=sys.stderr)
            return 2

        candidate_results = {r.case_id: r for r in evaluation_repository.list_results_for_run(db, run_id=candidate_run.id)}
        baseline_results = {r.case_id: r for r in evaluation_repository.list_results_for_run(db, run_id=baseline_run.id)}

        new_cases: list[str] = []
        fixed_cases: list[str] = []
        newly_failing_cases: list[str] = []
        still_failing_cases: list[str] = []
        for case_id, candidate_result in candidate_results.items():
            baseline_result = baseline_results.get(case_id)
            if baseline_result is None:
                new_cases.append(case_id)
            elif not baseline_result.passed and candidate_result.passed:
                fixed_cases.append(case_id)
            elif baseline_result.passed and not candidate_result.passed:
                newly_failing_cases.append(case_id)
            elif not baseline_result.passed and not candidate_result.passed:
                still_failing_cases.append(case_id)

        hard_safety_failures = [case_id for case_id, result in candidate_results.items() if result.hard_failure]

        policy = load_policy_from_env()
        candidate_summary = build_run_summary(db, run_id=candidate_run.id)
        baseline_summary = build_run_summary(db, run_id=baseline_run.id)
        verdict = evaluate_gate(candidate_summary, policy=policy, run_status=candidate_run.status, baseline=baseline_summary)

        report = {
            "run_id": candidate_run.id,
            "baseline_run_id": baseline_run.id,
            "dataset_id": candidate_run.dataset_id,
            "dataset_version": candidate_run.dataset_version,
            "baseline_dataset_version": baseline_run.dataset_version,
            "new_cases": new_cases,
            "fixed_cases": fixed_cases,
            "newly_failing_cases": newly_failing_cases,
            "still_failing_cases": still_failing_cases,
            "hard_safety_failures": hard_safety_failures,
            "candidate_summary": candidate_summary.as_dict(),
            "baseline_summary": baseline_summary.as_dict(),
            "citation_coverage_delta": candidate_summary.citation_coverage - baseline_summary.citation_coverage,
            "fallback_rate_delta": (
                (candidate_summary.fallback_rate_on_answerable or 0.0) - (baseline_summary.fallback_rate_on_answerable or 0.0)
                if candidate_summary.fallback_rate_on_answerable is not None or baseline_summary.fallback_rate_on_answerable is not None
                else None
            ),
            "latency_p95_delta_ms": (
                (candidate_summary.latency_p95_ms or 0) - (baseline_summary.latency_p95_ms or 0)
                if candidate_summary.latency_p95_ms is not None or baseline_summary.latency_p95_ms is not None
                else None
            ),
        }

        evaluation_candidate_repository.create_regression_report(
            db,
            organisation_id=args.organisation,
            workspace_id=args.workspace,
            widget_id=candidate_run.widget_id,
            dataset_id=candidate_run.dataset_id,
            run_id=candidate_run.id,
            baseline_run_id=baseline_run.id,
            report=report,
            verdict_passed=verdict.passed,
            verdict_reasons=verdict.reasons,
            created_by=args.created_by,
        )

        print(json.dumps({"verdict": verdict.as_dict(), "report": report}, indent=2, default=str))

    if args.gate and not verdict.passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
