"""CLI: report on (and optionally gate) an already-completed evaluation run.

    python -m app.operations.eval_report --run <id> --organisation <id> --workspace <id> \
        [--format text|json] [--baseline <run_id>] [--gate]

Exits 0 normally; with --gate, exits 1 if the run fails the regression gate
(useful for re-checking an older run against updated policy thresholds).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.report import render_json_report, render_text_report
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report on a completed evaluation run.")
    parser.add_argument("--run", required=True, help="Evaluation run id.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--baseline", default=None, help="Optional baseline run id to compare against.")
    parser.add_argument("--gate", action="store_true", help="Exit 1 if the run fails the regression gate.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with SessionLocal() as db:
        run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.run)
        if run is None:
            print(f"Run {args.run} not found.", file=sys.stderr)
            return 2

        summary = build_run_summary(db, run_id=run.id)
        baseline_summary = None
        if args.baseline:
            baseline_run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.baseline)
            if baseline_run is None:
                print(f"Baseline run {args.baseline} not found.", file=sys.stderr)
                return 2
            baseline_summary = build_run_summary(db, run_id=baseline_run.id)

        gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status, baseline=baseline_summary)

        if args.format == "json":
            print(json.dumps(render_json_report(run, summary, gate), indent=2, default=str))
        else:
            print(render_text_report(run, summary, gate))

    if args.gate and not gate.passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
