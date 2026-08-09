"""CLI: recalibrate RETRIEVAL_MIN_SIMILARITY_SCORE for the structure_aware
chunking strategy against the chunking-focused corpus (chunking_dataset.json),
using real embeddings. See docs/engineering/chunking.md and ADR-0032.

The existing calibration (docs/04_Engineering/Evaluation_Score_Distribution_Analysis.md,
`_VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL["nomic-embed-text-v2-moe"] = 0.25`)
was derived against golden_dataset.json's one-chunk-per-document
representation (whole ~50-word documents embedded as a single chunk each).
Since structure_aware chunking produces shorter, topically-narrower chunks
(63 words average on chunking_dataset.json - see the Knowledge Pipeline V2
bake-off report), that threshold's calibration basis no longer matches what
retrieval actually scores against in production. This script re-runs the
SAME two-phase methodology (raw score-distribution analysis, then controlled
threshold experiments) `eval_score_distribution.py` used, but seeds
chunking_dataset.json through the real `structure_aware` chunker instead of
reading a pre-seeded persistent dataset.

Phase 1 (score distribution): seeds the corpus once, then calls
`search_embedded_chunks` directly with a limit larger than the whole corpus
for every case, bucketing (query, chunk) pairs as relevant/irrelevant by
category - reuses `eval_score_distribution._percentile`/`_distribution_report`
directly so the statistics are computed identically to the existing
methodology.

Phase 2 (threshold experiments): candidate thresholds are DERIVED from
Phase 1's actual percentiles (never hardcoded up front - see
`_derive_candidate_thresholds`), then a FULL evaluation run
(`run_evaluation`/`evaluate_gate`) is executed once per candidate against the
SAME seeded corpus - strategy, config, corpus, and embeddings are held fixed;
only `min_similarity_score` varies between runs (the one-variable-at-a-time
requirement). The embedding provider is wrapped with the same exact-text
cache `eval_chunking_bakeoff.py` uses, shared across every candidate in this
run, so only the FIRST candidate pays for real (uncached) embedding calls -
retrieval and query embeddings are identical across thresholds, only which
chunks clear the cutoff changes.

    python -m app.operations.eval_chunking_threshold_calibration [--format text|json] [--keep-db]

Requires EVAL_EMBEDDING_PROVIDER/EVAL_EMBEDDING_MODEL set to a real provider
(e.g. ollama/nomic-embed-text-v2-moe) - this analysis is meaningless against
the mock provider's hash-based vectors.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Chunk, Membership, Organisation, User, Workspace
from app.evaluation.embedding_config import build_real_eval_embedding_provider
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.operations.eval_score_distribution import _distribution_report, _print_text_report as _print_distribution_text_report
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.services.vector_search import search_embedded_chunks

STRATEGY_KEY = "structure_aware"
CHUNKING_CONFIG = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
ISOLATION_CATEGORIES = {"cross_assistant_leakage", "cross_workspace_leakage", "cross_organisation_leakage"}


class _CachingEmbeddingProvider:
    """Same rationale/behavior as eval_chunking_bakeoff._CountingEmbeddingProvider
    - exact-text cache so repeated embed() calls for the same (model, text)
    pair (inevitable: SQLite's _search_sqlite re-embeds every candidate chunk
    on every query) cost one real network call instead of one per call, and
    so that re-running the full evaluation at each candidate threshold below
    only pays the real embedding cost once, not once per threshold."""

    def __init__(self, inner: EmbeddingProvider) -> None:
        self._inner = inner
        self.call_count = 0
        self._cache: dict[str, list[float]] = {}

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def dimension(self) -> int:
        return self._inner.dimension

    def embed(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        self.call_count += 1
        vector = self._inner.embed(text)
        self._cache[text] = vector
        return vector


@dataclass
class ThresholdExperimentResult:
    threshold: float
    total_cases: int
    passed_cases: int
    hard_failure_cases: int
    pass_rate: float
    retrieval_hit_rate: float | None
    average_recall_at_k: float | None
    citation_coverage: float | None
    fallback_rate_on_answerable: float | None
    correct_fallback_rate_on_unanswerable: float | None
    false_negative_rate: float | None  # from the Phase 1 raw score sweep at this exact threshold
    false_positive_rate: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_tokens: int
    gate_passed: bool
    gate_reasons: list[str] = field(default_factory=list)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recalibrate RETRIEVAL_MIN_SIMILARITY_SCORE for structure_aware chunking on chunking_dataset.json.")
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the temp SQLite file afterwards.")
    return parser.parse_args(argv)


def _build_embedding_provider() -> EmbeddingProvider:
    try:
        return build_real_eval_embedding_provider()
    except EmbeddingProviderError as exc:
        raise SystemExit(f"Cannot run threshold calibration: {exc}") from exc


def _derive_candidate_thresholds(overall: dict) -> list[float]:
    """Derived from Phase 1's actual observed percentiles, not chosen up
    front - mirrors the same midpoint methodology already used elsewhere in
    this codebase (app.services.chunking_strategies.semantic's
    DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD, and this same model's original
    golden-dataset calibration): candidates span from a permissive floor
    through the incumbent value to an aggressive ceiling, all read off the
    real relevant/irrelevant distributions computed in this same run."""
    relevant = overall["relevant"]
    irrelevant = overall["irrelevant"]
    candidates = {
        0.0,  # current production default (settings.RETRIEVAL_MIN_SIMILARITY_SCORE) - reference floor
        0.25,  # incumbent evaluation-calibrated value under test, not assumed correct
    }
    for key in ("p10", "p25", "p50"):
        if relevant[key] is not None:
            candidates.add(round(relevant[key], 2))
    for key in ("p75", "p90", "p95"):
        if irrelevant[key] is not None:
            candidates.add(round(irrelevant[key], 2))
    if relevant["p10"] is not None and irrelevant["p95"] is not None:
        candidates.add(round((relevant["p10"] + irrelevant["p95"]) / 2, 2))
    return sorted(value for value in candidates if 0.0 <= value <= 1.0)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    real_provider = _build_embedding_provider()
    provider = _CachingEmbeddingProvider(real_provider)
    strategy = build_chunking_strategy(STRATEGY_KEY, embedding_provider=None)

    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-chunking-threshold-calibration-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    try:
        with session_factory() as db:
            organisation = Organisation(name="Threshold Calibration", slug=f"threshold-calibration-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="threshold-calibration@example.test", full_name="Calibration")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db,
                organisation=organisation,
                workspace=workspace,
                embedding_provider=provider,
                actor_user_id=user.id,
                fixture=load_chunking_fixture_definition(),
                chunking_strategy=strategy,
                chunking_config=CHUNKING_CONFIG,
            )
            chunk_count = len(db.execute(select(Chunk).where(Chunk.organisation_id == organisation.id)).scalars().all())
            cases = list(loaded.dataset.cases)
            scope_document_ids = list(loaded.document_ids.values())

            # --- Phase 1: raw score distribution -----------------------------
            by_category: dict[str, dict[str, list[float]]] = {}
            overall_relevant: list[float] = []
            overall_irrelevant: list[float] = []
            for case in cases:
                if case.category in ISOLATION_CATEGORIES:
                    continue
                matches = search_embedded_chunks(
                    db,
                    organisation_id=organisation.id,
                    workspace_id=workspace.id,
                    query=case.question,
                    limit=max(chunk_count, 50),
                    provider=provider,
                    document_ids=scope_document_ids,
                )
                expected_document_ids = set(case.expected_document_ids or [])
                bucket = by_category.setdefault(case.category, {"relevant": [], "irrelevant": []})
                for match in matches:
                    if expected_document_ids and match.document_id in expected_document_ids:
                        bucket["relevant"].append(match.score)
                        overall_relevant.append(match.score)
                    else:
                        bucket["irrelevant"].append(match.score)
                        overall_irrelevant.append(match.score)

            distribution_report = {
                "embedding_provider": provider.provider_name,
                "embedding_model": provider.model_name,
                "embedding_dimension": provider.dimension,
                "skipped_cases": [],
                "overall": _distribution_report(overall_relevant, overall_irrelevant),
                "by_category": {
                    category: _distribution_report(scores["relevant"], scores["irrelevant"]) for category, scores in sorted(by_category.items())
                },
            }

            # --- Phase 2: controlled threshold experiments -------------------
            candidates = _derive_candidate_thresholds(distribution_report["overall"])
            sweep_by_threshold = {row["threshold"]: row for row in distribution_report["overall"]["threshold_sweep"]}

            experiment_results: list[ThresholdExperimentResult] = []
            for threshold in candidates:
                run = run_evaluation(
                    db,
                    dataset=loaded.dataset,
                    organisation_id=organisation.id,
                    workspace_id=workspace.id,
                    widget_id=loaded.widget_id,
                    options=EvaluationRunOptions(
                        mode="mock",
                        policy=load_policy_from_env(),
                        shadow_database_url=database_url,
                        embedding_provider=provider,
                        min_similarity_score=threshold,
                        case_timeout_seconds=180.0,
                    ),
                )
                summary = build_run_summary(db, run_id=run.id)
                gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)
                nearest_sweep = sweep_by_threshold.get(round(threshold / 0.05) * 0.05)
                experiment_results.append(
                    ThresholdExperimentResult(
                        threshold=threshold,
                        total_cases=summary.total_cases,
                        passed_cases=summary.passed_cases,
                        hard_failure_cases=summary.hard_failure_cases,
                        pass_rate=summary.pass_rate,
                        retrieval_hit_rate=summary.retrieval_hit_rate,
                        average_recall_at_k=summary.average_recall_at_k,
                        citation_coverage=summary.citation_coverage,
                        fallback_rate_on_answerable=summary.fallback_rate_on_answerable,
                        correct_fallback_rate_on_unanswerable=summary.correct_fallback_rate_on_unanswerable,
                        false_negative_rate=nearest_sweep["false_negative_rate"] if nearest_sweep else None,
                        false_positive_rate=nearest_sweep["false_positive_rate"] if nearest_sweep else None,
                        latency_p50_ms=summary.latency_p50_ms,
                        latency_p95_ms=summary.latency_p95_ms,
                        total_tokens=summary.total_tokens,
                        gate_passed=gate.passed,
                        gate_reasons=list(gate.reasons),
                    )
                )

    finally:
        engine.dispose()
        if temp_db_path.exists() and not args.keep_db:
            temp_db_path.unlink()

    if args.format == "json":
        print(json.dumps({"distribution": distribution_report, "experiments": [asdict(r) for r in experiment_results]}, indent=2, default=str))
    else:
        _print_distribution_text_report(distribution_report)
        _print_experiment_report(experiment_results)

    return 0


def _print_experiment_report(results: list[ThresholdExperimentResult]) -> None:
    print("=== THRESHOLD EXPERIMENTS (structure_aware, chunking_dataset.json, real embeddings) ===")
    header = (
        f"{'threshold':>9s} {'pass_rate':>9s} {'hard_fail':>9s} {'hit_rate':>9s} {'recall@k':>9s} {'citation':>9s} "
        f"{'fallback':>9s} {'correct_fb':>10s} {'fnr':>6s} {'fpr':>6s} {'p50/p95 ms':>12s} {'tokens':>8s} {'gate':>6s}"
    )
    print(header)
    for r in results:
        hit_rate = f"{r.retrieval_hit_rate:.1%}" if r.retrieval_hit_rate is not None else "n/a"
        recall = f"{r.average_recall_at_k:.1%}" if r.average_recall_at_k is not None else "n/a"
        citation = f"{r.citation_coverage:.1%}" if r.citation_coverage is not None else "n/a"
        fallback = f"{r.fallback_rate_on_answerable:.1%}" if r.fallback_rate_on_answerable is not None else "n/a"
        correct_fb = f"{r.correct_fallback_rate_on_unanswerable:.1%}" if r.correct_fallback_rate_on_unanswerable is not None else "n/a"
        fnr = f"{r.false_negative_rate:.0%}" if r.false_negative_rate is not None else "n/a"
        fpr = f"{r.false_positive_rate:.0%}" if r.false_positive_rate is not None else "n/a"
        latency = f"{r.latency_p50_ms or 0}/{r.latency_p95_ms or 0}"
        print(
            f"{r.threshold:9.2f} {r.pass_rate:8.1%} {r.hard_failure_cases:9d} {hit_rate:>9s} {recall:>9s} {citation:>9s} "
            f"{fallback:>9s} {correct_fb:>10s} {fnr:>6s} {fpr:>6s} {latency:>12s} {r.total_tokens:8d} {'PASS' if r.gate_passed else 'FAIL':>6s}"
        )
    print()


if __name__ == "__main__":
    raise SystemExit(main())
