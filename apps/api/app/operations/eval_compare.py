"""CLI: compare two evaluation runs (baseline vs candidate) - deterministic
metrics always, optionally grader-score deltas too.

    python -m app.operations.eval_compare --baseline <id> --candidate <id> --organisation <id> --workspace <id>
    python -m app.operations.eval_compare --baseline <id> --candidate <id> --organisation <id> --workspace <id> --grader
    python -m app.operations.eval_compare --baseline <id> --candidate <id> --organisation <id> --workspace <id> --format json

`--grader` requires both runs to have already been graded (via eval_grade.py)
- it reports the per-dimension average-score delta between the two runs and
  explicitly separates that from the deterministic metric delta (Section 9's
  "compare reports distinguish deterministic changes from grader-score
  changes"). It never re-runs grading itself.

Exits 0 normally, 2 on an operational error (run not found).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.evaluation.gate import evaluate_gate
from app.evaluation.graders.grading_report import build_grading_summary
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare a baseline evaluation run against a candidate run.")
    parser.add_argument("--baseline", required=True, help="Baseline run id.")
    parser.add_argument("--candidate", required=True, help="Candidate run id.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--grader", action="store_true", help="Also report grader-score deltas (requires both runs already graded via eval_grade.py).")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with SessionLocal() as db:
        baseline_run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.baseline)
        candidate_run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.candidate)
        if baseline_run is None:
            print(f"Baseline run {args.baseline} not found.", file=sys.stderr)
            return 2
        if candidate_run is None:
            print(f"Candidate run {args.candidate} not found.", file=sys.stderr)
            return 2

        baseline_summary = build_run_summary(db, run_id=baseline_run.id)
        candidate_summary = build_run_summary(db, run_id=candidate_run.id)
        gate = evaluate_gate(candidate_summary, policy=load_policy_from_env(), run_status=candidate_run.status, baseline=baseline_summary)

        deterministic_delta = {
            "pass_rate": _delta(baseline_summary.pass_rate, candidate_summary.pass_rate),
            "hard_failure_cases": candidate_summary.hard_failure_cases - baseline_summary.hard_failure_cases,
            "retrieval_hit_rate": _delta(baseline_summary.retrieval_hit_rate, candidate_summary.retrieval_hit_rate),
            "citation_coverage": _delta(baseline_summary.citation_coverage, candidate_summary.citation_coverage),
        }

        payload = {
            "baseline_run_id": baseline_run.id, "candidate_run_id": candidate_run.id,
            "deterministic_delta": deterministic_delta, "gate": gate.as_dict(),
        }

        if args.grader:
            baseline_grading = build_grading_summary(db, run_id=baseline_run.id)
            candidate_grading = build_grading_summary(db, run_id=candidate_run.id)
            grader_delta = {}
            for dim_name in set(baseline_grading.dimensions) | set(candidate_grading.dimensions):
                base_avg = baseline_grading.dimensions.get(dim_name).average_score if dim_name in baseline_grading.dimensions else None
                cand_avg = candidate_grading.dimensions.get(dim_name).average_score if dim_name in candidate_grading.dimensions else None
                grader_delta[dim_name] = {"baseline_avg": base_avg, "candidate_avg": cand_avg, "delta": _delta(base_avg, cand_avg)}
            payload["grader_score_delta"] = grader_delta
            payload["grader_disclaimer"] = "Grader-score deltas are model-generated estimates, advisory only - never used to override the deterministic_delta/gate verdict above."

        if args.format == "json":
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(f"Comparing baseline {baseline_run.id} -> candidate {candidate_run.id}")
            print(f"  pass_rate delta: {_fmt(deterministic_delta['pass_rate'])}")
            print(f"  hard_failure_cases delta: {deterministic_delta['hard_failure_cases']:+d}")
            print(f"  retrieval_hit_rate delta: {_fmt(deterministic_delta['retrieval_hit_rate'])}")
            print(f"  citation_coverage delta: {_fmt(deterministic_delta['citation_coverage'])}")
            print(f"  gate: {'PASSED' if gate.passed else 'FAILED'} ({'; '.join(gate.reasons) if gate.reasons else 'no issues'})")
            if args.grader:
                print("\n  Grader-score deltas (model-generated estimates, advisory only):")
                for dim_name, delta in payload["grader_score_delta"].items():
                    print(f"    {dim_name:<28} baseline={_fmt(delta['baseline_avg'])} candidate={_fmt(delta['candidate_avg'])} delta={_fmt(delta['delta'])}")

    return 0


def _delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return after - before


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
