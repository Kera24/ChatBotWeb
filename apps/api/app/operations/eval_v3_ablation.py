"""CLI: Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md),
Part 16 - the ablation matrix. Never just "baseline vs everything": each
variant below adds exactly one more layer than the previous one, so a
promotion decision can attribute any observed gain (or regression) to a
SPECIFIC component instead of crediting the whole stack.

    python -m app.operations.eval_v3_ablation [--format text|json] [--real] [--keep-db] [--corpus golden|chunking|both] [--skip-reranker]

Variants (Part 16's own lettering):
  A  dense_only baseline - today's exact production candidate (structure_aware,
     dense_only, threshold 0.32, identity query transform, no reranker,
     Evidence Sufficiency V2). B (dense+HNSW) is NOT run here - pgvector HNSW
     has no SQLite equivalent (this evaluation framework's fixtures always
     run on a temp SQLite database, matching every other bake-off script in
     this project - see app.evaluation.fixtures.loader), so it is measured
     separately and empirically by app.operations.eval_hnsw_benchmark against
     a real Postgres/pgvector database; that script's own result (perfect
     exact-vs-ANN agreement on this corpus size) is what lets this report
     state B's answer-quality is identical to A's without re-running it here.
  C  hybrid_rrf (existing Retrieval V2 Phase 1 dense+lexical+RRF fusion,
     RETRIEVAL_STRATEGY=hybrid_rrf) - no reranker yet.
  D  hybrid_rrf + reranker (existing Retrieval V2 Phase 2 cross-encoder,
     RERANKER_PROVIDER=cross_encoder) - candidate-order change only, still no
     evidence-confidence/constraints stage.
  E  V3 candidate (use_v3_retrieval=True: hybrid dense+lexical+RRF+reranker
     with full per-chunk provenance, PLUS the new Evidence Confidence /
     AnswerConstraints stage) - the full "B" bundle Part 14 describes.
  F  V3 + caching - NOT run through this evaluation framework either (a
     retrieval cache's entire value proposition is repeat traffic across
     separate requests, which a single evaluation pass over N distinct
     questions cannot exercise meaningfully); measured separately by
     app.operations.eval_v3_cache_benchmark, which replays the same query set
     twice to produce a real hit rate.

Requires `--real` for a meaningful comparison (mock embeddings carry no
semantic signal - see every other bake-off script in this project for the
same caveat). `--skip-reranker` skips variants D/E if the optional
`sentence-transformers` dependency is not installed, printing a clear
message rather than crashing (Part 8's "keep the V3 pipeline experimental
rather than bloating the default deployment").
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.embedding_cache import CachingEmbeddingProvider
from app.evaluation.embedding_config import (
    build_real_eval_embedding_provider,
    load_eval_embedding_config_from_env,
    recommended_min_similarity_score,
)
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider
from app.services.reranking import CROSS_ENCODER_PROVIDER, NO_RERANKER_PROVIDER, RerankerUnavailableError, build_reranker
from app.services.retrieval_context import DENSE_ONLY_STRATEGY, HYBRID_RRF_STRATEGY


@dataclass(frozen=True)
class Variant:
    label: str
    retrieval_strategy: str | None
    reranker_provider: str
    use_v3_retrieval: bool


@dataclass
class VariantResult:
    label: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    hard_failure_cases: int
    pass_rate: float
    retrieval_hit_rate: float | None
    average_recall_at_k: float | None
    average_precision_at_k: float | None
    average_evidence_coverage: float | None
    citation_coverage: float | None
    fallback_rate_on_answerable: float | None
    correct_fallback_rate_on_unanswerable: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_tokens: int
    gate_passed: bool
    gate_reasons: list[str] = field(default_factory=list)
    category_pass_rate: dict[str, float] = field(default_factory=dict)
    failure_reason_counts: dict[str, int] = field(default_factory=dict)
    run_seconds: float = 0.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieval & Answer Pipeline V3 - Part 16 ablation matrix (A/C/D/E; B/F measured separately, see module docstring).")
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument("--real", action="store_true", help="Use EVAL_EMBEDDING_PROVIDER/MODEL instead of the deterministic mock.")
    parser.add_argument("--keep-db", action="store_true")
    parser.add_argument("--corpus", default="both", choices=["golden", "chunking", "both"])
    parser.add_argument("--skip-reranker", action="store_true", help="Skip variants D/E (reranker-dependent) - use if sentence-transformers is not installed.")
    parser.add_argument("--case-timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def _build_embedding_provider(*, use_real: bool) -> tuple[EmbeddingProvider, float]:
    if use_real:
        try:
            provider = build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            raise SystemExit(f"Cannot run a real-embedding ablation: {exc}") from exc
        recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
        min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE
        return provider, min_similarity_score
    return build_embedding_provider(provider_name="local-mock", model_name="v3-ablation", dimension=8), settings.RETRIEVAL_MIN_SIMILARITY_SCORE


def _reranker_available() -> bool:
    try:
        build_reranker(provider_name=CROSS_ENCODER_PROVIDER, model_name=settings.RERANKER_MODEL)
        return True
    except RerankerUnavailableError:
        return False


def _category_pass_rates(db, *, run_id: str) -> dict[str, float]:
    totals: dict[str, int] = {}
    passed: dict[str, int] = {}
    for result in evaluation_repository.list_results_for_run(db, run_id=run_id):
        category = result.case.category if result.case is not None else "unknown"
        totals[category] = totals.get(category, 0) + 1
        if result.passed:
            passed[category] = passed.get(category, 0) + 1
    return {category: passed.get(category, 0) / total for category, total in totals.items()}


def _failure_reason_counts(db, *, run_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in evaluation_repository.list_results_for_run(db, run_id=run_id):
        for reason in result.failure_reasons_json or []:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _run_corpus(*, corpus: str, variants: list[Variant], embedding_provider: EmbeddingProvider, min_similarity_score: float, case_timeout: float, keep_db: bool) -> list[VariantResult]:
    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-v3-ablation-{corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    cached_provider = CachingEmbeddingProvider(embedding_provider)
    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)
    if corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
    else:
        fixture = None
        chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

    results: list[VariantResult] = []
    try:
        with session_factory() as db:
            organisation = Organisation(name="V3 Ablation", slug=f"v3-ablation-{corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="v3-ablation@example.test", full_name="Ablation")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )

            for variant in variants:
                reranker = build_reranker(provider_name=variant.reranker_provider, model_name=settings.RERANKER_MODEL, timeout_seconds=settings.RERANKER_TIMEOUT_SECONDS)
                started_at = time.perf_counter()
                run = run_evaluation(
                    db, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id,
                    options=EvaluationRunOptions(
                        mode="mock",
                        policy=load_policy_from_env(),
                        shadow_database_url=database_url,
                        embedding_provider=cached_provider,
                        min_similarity_score=min_similarity_score,
                        case_timeout_seconds=case_timeout,
                        retrieval_strategy_override=variant.retrieval_strategy,
                        reranker_override=reranker,
                        use_v3_retrieval=variant.use_v3_retrieval,
                        trigger_source="v3_ablation",
                    ),
                )
                run_seconds = time.perf_counter() - started_at
                summary = build_run_summary(db, run_id=run.id)
                gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)
                results.append(
                    VariantResult(
                        label=variant.label, total_cases=summary.total_cases, passed_cases=summary.passed_cases,
                        failed_cases=summary.failed_cases, hard_failure_cases=summary.hard_failure_cases, pass_rate=summary.pass_rate,
                        retrieval_hit_rate=summary.retrieval_hit_rate, average_recall_at_k=summary.average_recall_at_k,
                        average_precision_at_k=summary.average_precision_at_k, average_evidence_coverage=getattr(summary, "average_evidence_coverage", None),
                        citation_coverage=summary.citation_coverage, fallback_rate_on_answerable=summary.fallback_rate_on_answerable,
                        correct_fallback_rate_on_unanswerable=summary.correct_fallback_rate_on_unanswerable,
                        latency_p50_ms=summary.latency_p50_ms, latency_p95_ms=summary.latency_p95_ms, total_tokens=summary.total_tokens,
                        gate_passed=gate.passed, gate_reasons=list(gate.reasons),
                        category_pass_rate=_category_pass_rates(db, run_id=run.id), failure_reason_counts=_failure_reason_counts(db, run_id=run.id),
                        run_seconds=run_seconds,
                    )
                )
            print(f"# corpus={corpus} documents={len(loaded.document_ids)} embedding_cache_stats={cached_provider.stats()}", file=sys.stderr, flush=True)
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()
    return results


def _print_text_report(all_results: dict[str, list[VariantResult]], *, embedding_provider: EmbeddingProvider, min_similarity_score: float) -> None:
    print(f"Retrieval & Answer Pipeline V3 - Part 16 ablation matrix - embedding provider: {embedding_provider.provider_name}/{embedding_provider.model_name} - min_similarity_score: {min_similarity_score}")
    print()
    for corpus, results in all_results.items():
        print(f"=== corpus: {corpus} ===")
        header = f"{'variant':10s} {'pass_rate':>9s} {'hard_fail':>9s} {'hit_rate':>9s} {'recall@k':>9s} {'precision@k':>11s} {'citation':>9s} {'fallback':>9s} {'p50/p95 ms':>12s} {'tokens':>8s} {'run_s':>7s} {'gate':>7s}"
        print(header)
        for r in results:
            hit_rate = f"{r.retrieval_hit_rate:.1%}" if r.retrieval_hit_rate is not None else "n/a"
            recall = f"{r.average_recall_at_k:.1%}" if r.average_recall_at_k is not None else "n/a"
            precision = f"{r.average_precision_at_k:.1%}" if r.average_precision_at_k is not None else "n/a"
            citation = f"{r.citation_coverage:.1%}" if r.citation_coverage is not None else "n/a"
            fallback = f"{r.fallback_rate_on_answerable:.1%}" if r.fallback_rate_on_answerable is not None else "n/a"
            latency = f"{r.latency_p50_ms or 0}/{r.latency_p95_ms or 0}"
            print(
                f"{r.label:10s} {r.pass_rate:8.1%} {r.hard_failure_cases:9d} {hit_rate:>9s} {recall:>9s} {precision:>11s} "
                f"{citation:>9s} {fallback:>9s} {latency:>12s} {r.total_tokens:8d} {r.run_seconds:7.1f} {'PASS' if r.gate_passed else 'FAIL':>7s}"
            )
            print(f"    category_pass_rate: {{{', '.join(f'{k}: {v:.0%}' for k, v in sorted(r.category_pass_rate.items()))}}}")
            print(f"    failure_reason_counts: {r.failure_reason_counts}")
        if len(results) >= 2:
            baseline = results[0]
            for candidate in results[1:]:
                pass_delta = candidate.pass_rate - baseline.pass_rate
                hard_delta = candidate.hard_failure_cases - baseline.hard_failure_cases
                print(f"  {candidate.label} vs {baseline.label}: pass_rate {pass_delta:+.1%}, hard_failures {hard_delta:+d}")
        print()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    embedding_provider, min_similarity_score = _build_embedding_provider(use_real=args.real)

    variants = [
        Variant(label="A_dense", retrieval_strategy=DENSE_ONLY_STRATEGY, reranker_provider=NO_RERANKER_PROVIDER, use_v3_retrieval=False),
        Variant(label="C_hybrid", retrieval_strategy=HYBRID_RRF_STRATEGY, reranker_provider=NO_RERANKER_PROVIDER, use_v3_retrieval=False),
    ]
    reranker_ok = not args.skip_reranker and _reranker_available()
    if reranker_ok:
        variants.append(Variant(label="D_hybrid_rerank", retrieval_strategy=HYBRID_RRF_STRATEGY, reranker_provider=CROSS_ENCODER_PROVIDER, use_v3_retrieval=False))
    else:
        print("# D_hybrid_rerank skipped (reranker not available) - E_v3 still runs, without reranking, per Part 8's 'keep V3 experimental, not a hard dependency'.", file=sys.stderr)
    variants.append(Variant(label="E_v3", retrieval_strategy=None, reranker_provider=CROSS_ENCODER_PROVIDER if reranker_ok else NO_RERANKER_PROVIDER, use_v3_retrieval=True))

    corpora = ["golden", "chunking"] if args.corpus == "both" else [args.corpus]
    all_results: dict[str, list[VariantResult]] = {}
    for corpus in corpora:
        all_results[corpus] = _run_corpus(
            corpus=corpus, variants=variants, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score,
            case_timeout=args.case_timeout, keep_db=args.keep_db,
        )

    if args.format == "json":
        print(json.dumps({
            "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name},
            "min_similarity_score": min_similarity_score,
            "results": {corpus: [asdict(r) for r in results] for corpus, results in all_results.items()},
        }, indent=2, default=str))
    else:
        _print_text_report(all_results, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
