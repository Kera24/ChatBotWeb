"""CLI: run an evaluation dataset against one assistant.

    python -m app.operations.eval_run --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--mode mock|live] [--format text|json] [--category <category>]

`--category` restricts the run to cases in a single category (e.g.
`citation_required`) for fast, focused iteration while diagnosing or fixing a
specific failure class, without paying for a full-dataset run every time.

Exits 0 once the run completes (regardless of pass/fail - use `eval_report.py
--gate` or `eval_launch.py` to enforce a release gate), 2 on an operational
error (dataset not found, empty dataset, empty category).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.evaluation.engine import EmptyDatasetError, EvaluationRunOptions, run_evaluation
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.report import render_json_report, render_text_report
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an evaluation dataset against one assistant.")
    parser.add_argument("--dataset", required=True, help="Evaluation dataset id.")
    parser.add_argument("--assistant", required=True, help="Assistant (widget) id to run against.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--mode", default="mock", choices=["mock", "live"], help="mock (deterministic, default) or live (requires a configured provider).")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--category", default=None, help="Restrict the run to cases in a single category (e.g. citation_required).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with SessionLocal() as db:
        dataset = evaluation_repository.get_dataset(db, organisation_id=args.organisation, workspace_id=args.workspace, dataset_id=args.dataset)
        if dataset is None:
            print(f"Dataset {args.dataset} not found for that organisation/workspace.", file=sys.stderr)
            return 2

        try:
            run = run_evaluation(
                db,
                dataset=dataset,
                organisation_id=args.organisation,
                workspace_id=args.workspace,
                widget_id=args.assistant,
                options=EvaluationRunOptions(mode=args.mode, policy=load_policy_from_env(), category_filter=args.category),
            )
        except EmptyDatasetError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        summary = build_run_summary(db, run_id=run.id)
        gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)

        if args.format == "json":
            print(json.dumps(render_json_report(run, summary, gate), indent=2, default=str))
        else:
            print(render_text_report(run, summary, gate))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
