"""CLI: analyse real-embedding retrieval similarity-score distributions
across the golden dataset's case categories, to support a defensible
RETRIEVAL_MIN_SIMILARITY_SCORE choice (see
docs/04_Engineering/Evaluation_Score_Distribution_Analysis.md).

Unlike a normal evaluation run (which is capped to the top
RETRIEVAL_MAX_CONTEXT_CHUNKS matches per query), this script calls
`search_embedded_chunks` directly with a limit larger than the whole corpus,
so every chunk's raw score for every query is visible - not just whichever
ones would have made it into an assembled answer's context.

    python -m app.operations.eval_score_distribution --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--format text|json]

Requires the real embedding provider (EVAL_EMBEDDING_*) - this analysis is
meaningless against the deterministic mock provider's hash-based vectors (see
docs/04_Engineering/Evaluation_Task_Specification.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field

from app.access.widget_admin.service import get_current_draft, get_widget
from app.db.session import SessionLocal
from app.evaluation.embedding_config import build_real_eval_embedding_provider
from app.repositories import evaluation_repository
from app.services.embeddings import EmbeddingProviderError
from app.services.vector_search import search_embedded_chunks

_PERCENTILES = (0, 10, 25, 50, 75, 90, 95, 100)
_CANDIDATE_THRESHOLDS = [round(0.05 * i, 2) for i in range(1, 15)]  # 0.05 .. 0.70


@dataclass
class _CategoryScores:
    relevant: list[float] = field(default_factory=list)
    irrelevant: list[float] = field(default_factory=list)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyse real-embedding retrieval score distributions across the golden dataset.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--assistant", required=True)
    parser.add_argument("--organisation", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--format", default="text", choices=["text", "json"])
    return parser.parse_args(argv)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (percentile / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        embedding_provider = build_real_eval_embedding_provider()
    except EmbeddingProviderError as exc:
        print(f"Cannot analyse score distributions: {exc}", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        dataset = evaluation_repository.get_dataset(db, organisation_id=args.organisation, workspace_id=args.workspace, dataset_id=args.dataset)
        if dataset is None:
            print(f"Dataset {args.dataset} not found for that organisation/workspace.", file=sys.stderr)
            return 2
        cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=dataset.id)

        widget = get_widget(db, organisation_id=args.organisation, workspace_id=args.workspace, widget_id=args.assistant)
        draft = get_current_draft(db, widget=widget)
        scope_document_ids = list(draft.knowledge_scope_json or [])

        by_category: dict[str, _CategoryScores] = {}
        overall_relevant: list[float] = []
        overall_irrelevant: list[float] = []
        skipped_cases: list[str] = []

        for case in cases:
            if case.category in {"cross_assistant_leakage", "cross_workspace_leakage", "cross_organisation_leakage"}:
                continue  # isolation cases are scored by tenant-rejection, not similarity - not part of this analysis

            try:
                matches = search_embedded_chunks(
                    db,
                    organisation_id=args.organisation,
                    workspace_id=args.workspace,
                    query=case.question,
                    limit=max(len(scope_document_ids) * 2, 50),
                    provider=embedding_provider,
                    document_ids=scope_document_ids or None,
                )
            except Exception as exc:  # noqa: BLE001 - a single un-embeddable query (e.g. an empty string some
                # embedding models reject) must not abort the whole distribution analysis; skip and continue,
                # mirroring the evaluation engine's own per-case resilience (see app.evaluation.engine).
                skipped_cases.append(f"{case.id} ({case.category}): {exc}")
                continue
            expected_document_ids = set(case.expected_document_ids or [])
            bucket = by_category.setdefault(case.category, _CategoryScores())
            for match in matches:
                if expected_document_ids and match.document_id in expected_document_ids:
                    bucket.relevant.append(match.score)
                    overall_relevant.append(match.score)
                else:
                    bucket.irrelevant.append(match.score)
                    overall_irrelevant.append(match.score)

    report = {
        "embedding_provider": embedding_provider.provider_name,
        "embedding_model": embedding_provider.model_name,
        "embedding_dimension": embedding_provider.dimension,
        "skipped_cases": skipped_cases,
        "overall": _distribution_report(overall_relevant, overall_irrelevant),
        "by_category": {category: _distribution_report(scores.relevant, scores.irrelevant) for category, scores in sorted(by_category.items())},
    }

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        _print_text_report(report)
    return 0


def _distribution_report(relevant: list[float], irrelevant: list[float]) -> dict:
    relevant_stats = {f"p{p}": _percentile(relevant, p) for p in _PERCENTILES}
    irrelevant_stats = {f"p{p}": _percentile(irrelevant, p) for p in _PERCENTILES}

    threshold_sweep = []
    for threshold in _CANDIDATE_THRESHOLDS:
        false_negatives = sum(1 for score in relevant if score < threshold)
        false_positives = sum(1 for score in irrelevant if score >= threshold)
        threshold_sweep.append({
            "threshold": threshold,
            "false_negative_rate": (false_negatives / len(relevant)) if relevant else None,
            "false_positive_rate": (false_positives / len(irrelevant)) if irrelevant else None,
        })

    return {
        "relevant_count": len(relevant),
        "irrelevant_count": len(irrelevant),
        "relevant": relevant_stats,
        "irrelevant": irrelevant_stats,
        "threshold_sweep": threshold_sweep,
    }


def _print_text_report(report: dict) -> None:
    print(f"Embedding: {report['embedding_provider']}/{report['embedding_model']} (dimension {report['embedding_dimension']})")
    print()
    for scope_name, distribution in [("OVERALL", report["overall"]), *report["by_category"].items()]:
        print(f"=== {scope_name} ===")
        print(f"  relevant   (n={distribution['relevant_count']}): {distribution['relevant']}")
        print(f"  irrelevant (n={distribution['irrelevant_count']}): {distribution['irrelevant']}")
        print("  threshold sweep (threshold, false_negative_rate, false_positive_rate):")
        for row in distribution["threshold_sweep"]:
            print(f"    {row['threshold']:.2f}  fnr={row['false_negative_rate']}  fpr={row['false_positive_rate']}")
        print()


if __name__ == "__main__":
    raise SystemExit(main())
