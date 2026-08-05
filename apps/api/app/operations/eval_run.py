"""CLI: run an evaluation dataset against one assistant.

    python -m app.operations.eval_run --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--mode mock|live] [--format text|json] [--category <category>] [--real] [--min-similarity-score <float>]

`--category` restricts the run to cases in a single category (e.g.
`citation_required`) for fast, focused iteration while diagnosing or fixing a
specific failure class, without paying for a full-dataset run every time.

`--real` uses the real embedding provider configured via EVAL_EMBEDDING_* (see
docs/04_Engineering/Evaluation_Real_Embedding_Provider.md) instead of the
deterministic mock - it must exactly match whatever provider the target
dataset's chunks were seeded with (`eval_golden_setup.py --real`), since
retrieval filters by an exact (provider, model, dimension) match. Fails
clearly (no silent fallback to mock) if the real provider/runtime/model is
unavailable.

`--min-similarity-score` overrides RETRIEVAL_MIN_SIMILARITY_SCORE for just
this run, without touching the global environment - used for controlled
threshold experiments (one run per candidate threshold).

Exits 0 once the run completes (regardless of pass/fail - use `eval_report.py
--gate` or `eval_launch.py` to enforce a release gate), 2 on an operational
error (dataset not found, empty dataset, empty category, real provider not configured/unavailable).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.evaluation.embedding_config import build_real_eval_embedding_provider, load_eval_embedding_config_from_env, recommended_min_similarity_score
from app.evaluation.engine import EmptyDatasetError, EvaluationRunOptions, run_evaluation
from app.evaluation.gate import evaluate_gate
from app.services.embeddings import EmbeddingProviderError
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
    parser.add_argument("--real", action="store_true", help="Use the real embedding provider (EVAL_EMBEDDING_*) instead of the deterministic mock.")
    parser.add_argument("--min-similarity-score", type=float, default=None, help="Override RETRIEVAL_MIN_SIMILARITY_SCORE for just this run (for threshold experiments).")
    parser.add_argument("--case-timeout", type=float, default=30.0, help="Per-case timeout in seconds (default 30; real-embedding runs recompute every chunk's embedding live per query and may need more, e.g. 90-120).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    real_embedding_provider = None
    min_similarity_score = args.min_similarity_score
    if args.real:
        try:
            real_embedding_provider = build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            # Catches both EvalEmbeddingNotConfiguredError (a subclass, raised
            # for config-level problems - unset provider/model) and the base
            # EmbeddingProviderError (raised for runtime-level problems -
            # unreachable Ollama, model not installed) uniformly, so every
            # real-provider failure mode exits cleanly with an actionable
            # message instead of a raw traceback.
            print(f"Cannot run with --real: {exc}", file=sys.stderr)
            return 2
        if min_similarity_score is None:
            # Apply the evidence-based threshold for this model by default
            # (see docs/04_Engineering/Evaluation_Retrieval_Experiments.md) so
            # a real-embedding run is launch-representative out of the box,
            # without silently reverting to the provider-agnostic 0.0 default
            # that only makes sense for the mock provider. Still fully
            # overridable via --min-similarity-score for further experiments.
            recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
            if recommended is not None:
                min_similarity_score = recommended
                print(f"Using evidence-based RETRIEVAL_MIN_SIMILARITY_SCORE={recommended} for model {real_embedding_provider.model_name!r} (override with --min-similarity-score).", file=sys.stderr)

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
                options=EvaluationRunOptions(
                    mode=args.mode,
                    policy=load_policy_from_env(),
                    category_filter=args.category,
                    embedding_provider=real_embedding_provider,
                    min_similarity_score=min_similarity_score,
                    case_timeout_seconds=args.case_timeout,
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
