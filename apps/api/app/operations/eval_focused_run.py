"""CLI: run only the newly production-fed cases in a dataset instead of the
whole thing - the "failed/new-case focused evaluation" piece of the
production feedback loop (spec section 7).

    python -m app.operations.eval_focused_run --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--mode mock|live] [--format text|json] [--case-ids id1,id2 | --since-run <run_id>]

With neither `--case-ids` nor `--since-run`, runs every case in the dataset
that was promoted from a production EvaluationCandidate (`EvaluationCase.
source_candidate_id is not None`) - i.e. "all production-fed cases", the
useful default for "did the cases we've promoted from real failures actually
get fixed". `--since-run <run_id>` narrows that further to production-fed
cases created after the given baseline run completed, for "what's new since
the last scheduled run". `--case-ids` is an explicit override for either.

Sets EvaluationRun.trigger_source="focused" so the dashboard's Scheduled Runs
view can distinguish this from an ad-hoc full-dataset run.

Exits 0 once the run completes, 2 on an operational error (dataset/run not
found, empty selection).
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
    parser = argparse.ArgumentParser(description="Run only the newly production-fed cases in a dataset.")
    parser.add_argument("--dataset", required=True, help="Evaluation dataset id.")
    parser.add_argument("--assistant", required=True, help="Assistant (widget) id to run against.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--mode", default="mock", choices=["mock", "live"], help="mock (deterministic, default) or live (requires a configured provider).")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--case-ids", default=None, help="Comma-separated explicit case ids to run, overriding the default production-fed selection.")
    parser.add_argument("--since-run", default=None, help="Only run production-fed cases created after this baseline run id completed.")
    parser.add_argument("--case-timeout", type=float, default=30.0, help="Per-case timeout in seconds (default 30).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    with SessionLocal() as db:
        dataset = evaluation_repository.get_dataset(db, organisation_id=args.organisation, workspace_id=args.workspace, dataset_id=args.dataset)
        if dataset is None:
            print(f"Dataset {args.dataset} not found for that organisation/workspace.", file=sys.stderr)
            return 2

        if args.case_ids:
            case_ids = frozenset(part.strip() for part in args.case_ids.split(",") if part.strip())
        else:
            all_cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=dataset.id)
            production_fed = [case for case in all_cases if case.source_candidate_id is not None]
            if args.since_run:
                baseline_run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.since_run)
                if baseline_run is None:
                    print(f"Baseline run {args.since_run} not found for that organisation/workspace.", file=sys.stderr)
                    return 2
                cutoff = baseline_run.completed_at or baseline_run.created_at
                production_fed = [case for case in production_fed if case.created_at > cutoff]
            case_ids = frozenset(case.id for case in production_fed)

        if not case_ids:
            print("No production-fed cases matched the selection; nothing to run.", file=sys.stderr)
            return 2

        try:
            run = run_evaluation(
                db,
                dataset=dataset,
                organisation_id=args.organisation,
                workspace_id=args.workspace,
                widget_id=args.assistant,
                options=EvaluationRunOptions(
                    mode=args.mode,
                    policy=load_policy_from_env(),
                    case_ids=case_ids,
                    case_timeout_seconds=args.case_timeout,
                    trigger_source="focused",
                ),
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
