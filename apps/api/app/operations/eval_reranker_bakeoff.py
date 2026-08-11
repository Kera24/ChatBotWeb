"""CLI: Retrieval V2 Phase 2 controlled bake-off - dense_only baseline vs.
dense + local cross-encoder reranker, over the SAME corpus, chunking
strategy (structure_aware - the current production default, ADR-0031),
embedding model, calibrated similarity threshold, generation provider
(mock, for determinism across variants), prompts, guardrails and evaluation
criteria. Only the reranker configuration varies between runs. Reuses the
existing evaluation framework end to end (app.evaluation.engine.run_evaluation),
the same pattern as app.operations.eval_chunking_bakeoff - this script adds
no new scoring logic, it seeds the corpus once and re-runs evaluation
against it once per variant.

    python -m app.operations.eval_reranker_bakeoff [--format text|json] [--real] [--keep-db] [--corpus golden|chunking] [--include-hybrid]

Mock mode (default): deterministic, credential-free - proves the mechanics
end-to-end, but LocalMockEmbeddingProvider has no semantic content, so
reranking cannot show a genuine quality signal against it.

`--real`: uses EVAL_EMBEDDING_PROVIDER/EVAL_EMBEDDING_MODEL (must already be
set, e.g. ollama/nomic-embed-text-v2-moe) for a genuinely semantically
meaningful comparison, and applies this project's calibrated
RETRIEVAL_MIN_SIMILARITY_SCORE for that model (0.32 for
nomic-embed-text-v2-moe, docs/adr/0032) - the threshold itself is never
varied by this script.

Variants compared:
  dense_only      - the current production baseline, reranker disabled.
  dense_reranked  - dense_only's wider candidate pool, reranked by a local
                     cross-encoder (default cross-encoder/ms-marco-MiniLM-L-6-v2,
                     see docs/future/Reranking.md for the model selection
                     rationale).
  hybrid_reranked - (only with --include-hybrid) hybrid_rrf's fused pool,
                     reranked the same way. Exploratory only (Part 10) - never
                     promoted on its own, only looked at if dense_reranked
                     already clearly improves on dense_only.

Exits 0 regardless of any individual variant's gate result (this is a
comparison report, not a pass/fail gate) - see the printed promotion check
for the actual accept/reject call (Part 11 policy).
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Chunk, Membership, Organisation, User, Workspace
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
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider
from app.services.reranking import CROSS_ENCODER_PROVIDER, NO_RERANKER_PROVIDER, Reranker, build_reranker
from app.services.retrieval_context import DENSE_ONLY_STRATEGY, HYBRID_RRF_STRATEGY

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass(frozen=True)
class Variant:
    label: str
    retrieval_strategy: str
    reranker: Reranker


@dataclass
class VariantResult:
    label: str
    retrieval_strategy: str
    reranker_provider: str
    reranker_model: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    hard_failure_cases: int
    pass_rate: float
    retrieval_hit_rate: float | None
    citation_coverage: float | None
    fallback_rate_on_answerable: float | None
    correct_fallback_rate_on_unanswerable: float | None
    average_recall_at_k: float | None
    average_precision_at_k: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_tokens: int
    gate_passed: bool
    gate_reasons: list[str] = field(default_factory=list)
    failure_reason_counts: dict[str, int] = field(default_factory=dict)
    run_seconds: float = 0.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled bake-off: dense_only baseline vs. dense + cross-encoder reranker.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--real", action="store_true", help="Use EVAL_EMBEDDING_PROVIDER/MODEL (a real embedding runtime) instead of the deterministic mock.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the temp SQLite file afterwards.")
    parser.add_argument(
        "--corpus", default="golden", choices=["golden", "chunking"],
        help="'golden' (default): golden_dataset.json, the general launch/regression corpus (83 cases). "
        "'chunking': chunking_dataset.json, the structurally-rich corpus (104 cases).",
    )
    parser.add_argument("--include-hybrid", action="store_true", help="Also run the exploratory hybrid_rrf + reranker variant (Part 10).")
    parser.add_argument("--reranker-model", default=DEFAULT_RERANKER_MODEL, help="Cross-encoder model to evaluate.")
    parser.add_argument("--reranker-candidate-pool-size", type=int, default=None, help="Override RERANKER_DENSE_CANDIDATE_POOL_SIZE for this run (Part 9 experiments).")
    parser.add_argument("--reranker-final-top-k", type=int, default=None, help="Override RERANKER_FINAL_TOP_K for this run (Part 9 experiments).")
    return parser.parse_args(argv)


def _build_embedding_provider(*, use_real: bool) -> tuple[EmbeddingProvider, float]:
    if use_real:
        try:
            provider = build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            raise SystemExit(f"Cannot run a real-embedding bake-off: {exc}") from exc
        recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
        min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE
        return provider, min_similarity_score
    return build_embedding_provider(provider_name="local-mock", model_name="reranker-bakeoff", dimension=8), settings.RETRIEVAL_MIN_SIMILARITY_SCORE


def _run_all_variants(
    variants: list[Variant], *, embedding_provider: EmbeddingProvider, min_similarity_score: float, keep_db: bool, corpus: str,
    reranker_candidate_pool_size: int | None, reranker_final_top_k: int | None,
) -> list[VariantResult]:
    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-reranker-bakeoff-{corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    # Shared across every variant call below (see CachingEmbeddingProvider's
    # docstring) - the corpus and queries are identical between variants, so
    # a chunk's embedding computed for the dense_only run is reused for
    # dense_reranked/hybrid_reranked instead of being recomputed, the same
    # benefit a real pgvector deployment gets from storing vectors once.
    cached_provider = CachingEmbeddingProvider(embedding_provider)

    # ADR-0031: structure_aware is the current production chunking default -
    # held constant across every variant in this bake-off (only reranker
    # configuration varies), never re-litigated here.
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
            organisation = Organisation(name="Reranker Bakeoff", slug=f"reranker-bakeoff-{corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="reranker-bakeoff@example.test", full_name="Bakeoff")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )
            chunk_count = len(db.execute(select(Chunk).where(Chunk.organisation_id == organisation.id)).scalars().all())

            for variant in variants:
                started_at = time.perf_counter()
                run = run_evaluation(
                    db, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id,
                    options=EvaluationRunOptions(
                        mode="mock",
                        policy=load_policy_from_env(),
                        shadow_database_url=database_url,
                        embedding_provider=cached_provider,
                        min_similarity_score=min_similarity_score,
                        case_timeout_seconds=180.0 if corpus == "chunking" else 60.0,
                        retrieval_strategy_override=variant.retrieval_strategy,
                        reranker_override=variant.reranker,
                        reranker_candidate_pool_size=reranker_candidate_pool_size,
                        reranker_final_top_k=reranker_final_top_k,
                    ),
                )
                run_seconds = time.perf_counter() - started_at
                summary = build_run_summary(db, run_id=run.id)
                gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)
                failure_reason_counts = _failure_reason_counts(db, run_id=run.id)
                results.append(
                    VariantResult(
                        label=variant.label,
                        retrieval_strategy=variant.retrieval_strategy,
                        reranker_provider=variant.reranker.provider_name,
                        reranker_model=variant.reranker.model_name,
                        total_cases=summary.total_cases,
                        passed_cases=summary.passed_cases,
                        failed_cases=summary.failed_cases,
                        hard_failure_cases=summary.hard_failure_cases,
                        pass_rate=summary.pass_rate,
                        retrieval_hit_rate=summary.retrieval_hit_rate,
                        citation_coverage=summary.citation_coverage,
                        fallback_rate_on_answerable=summary.fallback_rate_on_answerable,
                        correct_fallback_rate_on_unanswerable=summary.correct_fallback_rate_on_unanswerable,
                        average_recall_at_k=summary.average_recall_at_k,
                        average_precision_at_k=summary.average_precision_at_k,
                        latency_p50_ms=summary.latency_p50_ms,
                        latency_p95_ms=summary.latency_p95_ms,
                        total_tokens=summary.total_tokens,
                        gate_passed=gate.passed,
                        gate_reasons=list(gate.reasons),
                        failure_reason_counts=failure_reason_counts,
                        run_seconds=run_seconds,
                    )
                )
            print(f"# corpus documents={len(loaded.document_ids)} chunks={chunk_count} cache_stats={cached_provider.stats()}", flush=True)
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()
    return results


def _failure_reason_counts(db, *, run_id: str) -> dict[str, int]:
    from app.repositories import evaluation_repository

    counts: dict[str, int] = {}
    for result in evaluation_repository.list_results_for_run(db, run_id=run_id):
        for reason in result.failure_reasons_json or []:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _print_text_report(results: list[VariantResult], *, embedding_provider: EmbeddingProvider, min_similarity_score: float, corpus: str) -> None:
    print(
        f"Retrieval V2 Phase 2 reranker bake-off - corpus: {corpus} - embedding provider: "
        f"{embedding_provider.provider_name}/{embedding_provider.model_name} - min_similarity_score: {min_similarity_score}"
    )
    print()
    header = (
        f"{'variant':18s} {'pass_rate':>9s} {'hard_fail':>9s} {'hit_rate':>9s} {'recall@k':>9s} {'precision@k':>11s} "
        f"{'citation':>9s} {'fallback':>9s} {'p50/p95 ms':>12s} {'tokens':>8s} {'run_s':>7s} {'gate':>7s}"
    )
    print(header)
    for r in results:
        hit_rate = f"{r.retrieval_hit_rate:.1%}" if r.retrieval_hit_rate is not None else "n/a"
        recall = f"{r.average_recall_at_k:.1%}" if r.average_recall_at_k is not None else "n/a"
        precision = f"{r.average_precision_at_k:.1%}" if r.average_precision_at_k is not None else "n/a"
        citation = f"{r.citation_coverage:.1%}" if r.citation_coverage is not None else "n/a"
        fallback = f"{r.fallback_rate_on_answerable:.1%}" if r.fallback_rate_on_answerable is not None else "n/a"
        latency = f"{r.latency_p50_ms or 0}/{r.latency_p95_ms or 0}"
        print(
            f"{r.label:18s} {r.pass_rate:8.1%} {r.hard_failure_cases:9d} {hit_rate:>9s} {recall:>9s} {precision:>11s} "
            f"{citation:>9s} {fallback:>9s} {latency:>12s} {r.total_tokens:8d} {r.run_seconds:7.1f} {'PASS' if r.gate_passed else 'FAIL':>7s}"
        )
    print()
    baseline = results[0]
    for candidate in results[1:]:
        print(f"--- {candidate.label} vs {baseline.label} ---")
        new_hard_failures = candidate.hard_failure_cases - baseline.hard_failure_cases
        pass_rate_delta = candidate.pass_rate - baseline.pass_rate
        hit_rate_delta = _delta(candidate.retrieval_hit_rate, baseline.retrieval_hit_rate)
        recall_delta = _delta(candidate.average_recall_at_k, baseline.average_recall_at_k)
        precision_delta = _delta(candidate.average_precision_at_k, baseline.average_precision_at_k)
        citation_delta = _delta(candidate.citation_coverage, baseline.citation_coverage)
        print(f"  hard_failure_cases delta: {new_hard_failures:+d}  pass_rate delta: {pass_rate_delta:+.1%}")
        print(f"  hit_rate delta: {_fmt(hit_rate_delta)}  recall@k delta: {_fmt(recall_delta)}  precision@k delta: {_fmt(precision_delta)}")
        print(f"  citation_coverage delta: {_fmt(citation_delta)}")
        print(f"  baseline failure_reason_counts: {baseline.failure_reason_counts}")
        print(f"  candidate failure_reason_counts: {candidate.failure_reason_counts}")
        # Part 11 promotion policy (necessary, not sufficient - see this
        # script's report for the human case-level judgement it still
        # requires): zero new hard failures, citation integrity maintained,
        # pass rate non-regressive, Precision@K materially improves, Recall@K
        # not unacceptably regressed.
        non_regressive = (
            new_hard_failures <= 0
            and pass_rate_delta >= -0.001
            and (citation_delta is None or citation_delta >= -0.001)
            and (recall_delta is None or recall_delta >= -0.02)
        )
        precision_materially_improved = precision_delta is not None and precision_delta >= 0.02
        print(f"  Part 11 promotion check: {'non-regressive' if non_regressive else 'REGRESSION'}, precision materially improved: {precision_materially_improved}")
    print()


def _delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None:
        return None
    return candidate - baseline


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.1%}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    embedding_provider, min_similarity_score = _build_embedding_provider(use_real=args.real)

    reranker = build_reranker(
        provider_name=CROSS_ENCODER_PROVIDER, model_name=args.reranker_model, timeout_seconds=settings.RERANKER_TIMEOUT_SECONDS
    )
    variants = [
        Variant(label="dense_only", retrieval_strategy=DENSE_ONLY_STRATEGY, reranker=build_reranker(provider_name=NO_RERANKER_PROVIDER)),
        Variant(label="dense_reranked", retrieval_strategy=DENSE_ONLY_STRATEGY, reranker=reranker),
    ]
    if args.include_hybrid:
        variants.append(Variant(label="hybrid_reranked", retrieval_strategy=HYBRID_RRF_STRATEGY, reranker=reranker))

    results = _run_all_variants(
        variants, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score, keep_db=args.keep_db, corpus=args.corpus,
        reranker_candidate_pool_size=args.reranker_candidate_pool_size, reranker_final_top_k=args.reranker_final_top_k,
    )

    if args.format == "json":
        print(
            json.dumps(
                {
                    "corpus": args.corpus,
                    "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name},
                    "min_similarity_score": min_similarity_score,
                    "results": [asdict(r) for r in results],
                },
                indent=2, default=str,
            )
        )
    else:
        _print_text_report(results, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score, corpus=args.corpus)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
