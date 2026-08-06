"""CLI: run optional LLM-based graders (app.evaluation.graders) against an
already-completed evaluation run's stored answers, or against the human
calibration set.

    python -m app.operations.eval_grade --run <id> --organisation <id> --workspace <id> [--format text|json]
    python -m app.operations.eval_grade --run <id> --organisation <id> --workspace <id> --dimension groundedness
    python -m app.operations.eval_grade --run <id> --organisation <id> --workspace <id> --failed-only
    python -m app.operations.eval_grade --run <id> --organisation <id> --workspace <id> --repetitions 3
    python -m app.operations.eval_grade --calibrate

Grading is entirely offline and additive: it reads EvaluationResult rows
already persisted by `eval_run.py` and writes only the nullable
`judge_scores_json` column - it never re-runs the assistant, never touches
deterministic pass/fail/hard_failure fields, and never runs automatically as
part of a normal evaluation run (see Grader_Architecture.md's "no grader
runs automatically at launch" policy).

Uses EVAL_GRADER_PROVIDER (default "mock") - set EVAL_GRADER_PROVIDER=ollama
and EVAL_GRADER_MODEL to grade with a real local model. Fails clearly (exit
2) if a real grader is requested but not actually configured/reachable - no
silent fallback to the mock provider.

Exits 0 on success (regardless of individual dimension scores - grading is
advisory, never gating - see Section 12), 2 on an operational error (run/
case not found, misconfigured grader provider).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.db.models.evaluation import EvaluationCase
from app.evaluation.graders.cache import GraderResultCache
from app.evaluation.graders.calibration import run_calibration
from app.evaluation.graders.config import build_mock_grader_provider, build_real_eval_grader_provider, load_eval_grader_config_from_env
from app.evaluation.graders.engine import GradingRunStats, grade_result
from app.evaluation.graders.errors import GraderNotConfiguredError, GraderProviderError
from app.evaluation.graders.grading_report import build_grading_summary, render_grading_text_report
from app.evaluation.graders.rubrics import RUBRICS, GraderDimension
from app.repositories import evaluation_repository


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run optional LLM-based graders against a completed evaluation run.")
    parser.add_argument("--run", default=None, help="Evaluation run id (required unless --calibrate).")
    parser.add_argument("--organisation", default=None, help="Organisation id (required unless --calibrate).")
    parser.add_argument("--workspace", default=None, help="Workspace id (required unless --calibrate).")
    parser.add_argument("--dimension", default=None, choices=[d.value for d in GraderDimension], help="Restrict grading to a single dimension.")
    parser.add_argument("--failed-only", action="store_true", help="Only grade cases that failed deterministic scoring.")
    parser.add_argument("--repetitions", type=int, default=1, help="Repeat each grading call this many times to measure consistency (Section 6).")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--calibrate", action="store_true", help="Run graders against the human calibration set instead of a stored run.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        config = load_eval_grader_config_from_env()
        provider = build_mock_grader_provider() if config.provider == "mock" else build_real_eval_grader_provider(config)
    except GraderNotConfiguredError as exc:
        print(f"Cannot run grading: {exc}", file=sys.stderr)
        return 2
    except GraderProviderError as exc:
        print(f"Grader provider error: {exc}", file=sys.stderr)
        return 2

    if args.calibrate:
        report = run_calibration(provider=provider)
        if args.format == "json":
            print(json.dumps(report.as_dict(), indent=2, default=str))
        else:
            print(f"Calibration report ({report.total_examples} examples, grader={provider.provider_key}/{provider.model_name})")
            for dim, _rows in report.per_dimension.items():
                print(f"  {dim:<28} agreement={report.agreement_rate(dim):.1%} gating_ready={report.meets_gating_threshold(dim)}")
        return 0

    if not (args.run and args.organisation and args.workspace):
        print("--run, --organisation, and --workspace are required unless --calibrate is set.", file=sys.stderr)
        return 2

    dimensions = (GraderDimension(args.dimension),) if args.dimension else tuple(RUBRICS.keys())
    cache = GraderResultCache()
    stats = GradingRunStats()

    with SessionLocal() as db:
        run = evaluation_repository.get_run(db, organisation_id=args.organisation, workspace_id=args.workspace, run_id=args.run)
        if run is None:
            print(f"Run {args.run} not found.", file=sys.stderr)
            return 2

        results = evaluation_repository.list_results_for_run(db, run_id=run.id, only_failed=args.failed_only)
        if not results:
            print("No results to grade for this run/filter.", file=sys.stderr)
            return 2

        for result in results:
            case = db.get(EvaluationCase, result.case_id)
            if case is None:
                continue
            grade_result(db, result=result, case=case, provider=provider, dimensions=dimensions, repetitions=args.repetitions, cache=cache, stats=stats)

        summary = build_grading_summary(db, run_id=run.id)

        if args.format == "json":
            print(json.dumps({**summary.as_dict(), "run_stats": stats.__dict__, "cache_stats": cache.stats()}, indent=2, default=str))
        else:
            print(render_grading_text_report(summary))
            print(f"\nGrader calls: {stats.total_calls} | errors: {stats.errors} | cache hits: {cache.stats()['hits']} | total latency: {stats.total_latency_ms:.0f}ms")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
