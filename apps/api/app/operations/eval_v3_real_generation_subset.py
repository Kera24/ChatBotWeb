"""CLI: Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md),
Part 14 - "run a bounded real OpenRouter subset only after deterministic
results justify it". This script is that bounded real-generation check: real
nomic-embed-text-v2-moe embeddings AND real OpenRouter generation (never
mock - see app.operations.eval_production_candidate_real_generation, the
prior task's equivalent script for the production baseline, which this
mirrors), run over a SMALL, capped subset of cases (default 20) comparing
the production baseline (dense_only, no reranker) against the V3 candidate
pipeline (use_v3_retrieval=True) - not the full corpus, to keep real-provider
spend and wall-clock time bounded for what is meant to be a confirmatory
check, not the primary evaluation (the primary evaluation is the deterministic
ablation matrix, app.operations.eval_v3_ablation, run with mock generation).

    python -m app.operations.eval_v3_real_generation_subset [--corpus golden|chunking] [--sample-size 20] [--format text|json]

Fails loud (SystemExit(2)) if either real provider is not genuinely
configured/reachable - never silently substitutes mock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.dependencies import create_ai_core
from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.embedding_cache import CachingEmbeddingProvider
from app.evaluation.embedding_config import build_real_eval_embedding_provider, load_eval_embedding_config_from_env, recommended_min_similarity_score
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProviderError
from app.services.reranking import CROSS_ENCODER_PROVIDER, NO_RERANKER_PROVIDER, RerankerUnavailableError, build_reranker


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V3 Part 14 - bounded real-generation subset comparing baseline vs V3.")
    parser.add_argument("--corpus", default="chunking", choices=["golden", "chunking"])
    parser.add_argument("--sample-size", type=int, default=20, help="Cap on cases per variant (cost/time control).")
    parser.add_argument("--case-timeout", type=float, default=90.0)
    parser.add_argument("--format", default="text", choices=["text", "json"])
    return parser.parse_args(argv)


def _verify_prerequisites():
    try:
        embedding_provider = build_real_eval_embedding_provider()
    except EmbeddingProviderError as exc:
        print(f"MISSING PREREQUISITE: real embedding provider not available: {exc}", file=sys.stderr)
        raise SystemExit(2)
    recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
    min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE

    if settings.AI_PROVIDER != "openrouter" or not settings.OPENROUTER_API_KEY or not settings.OPENROUTER_MODEL:
        print(f"MISSING PREREQUISITE: real OpenRouter generation not configured (AI_PROVIDER={settings.AI_PROVIDER!r}).", file=sys.stderr)
        raise SystemExit(2)
    ai_core = create_ai_core()
    from app.ai.service import AICoreGenerateInput

    try:
        execution_id = ai_core.accounting_service.create_execution_id()
        response = ai_core.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer", model_key=settings.DEFAULT_AI_MODEL_KEY,
                variables={"question": "Reply with exactly: OK", "context": "No context needed."},
                execution_id=execution_id, organisation_id="prereq-check", workspace_id="prereq-check",
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"MISSING PREREQUISITE: real OpenRouter generation call failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
    print(f"# prerequisite check passed - provider={response.provider_key} model={response.provider_model_name}", file=sys.stderr)
    return ai_core, embedding_provider, min_similarity_score


@dataclass
class SubsetResult:
    variant: str
    total_cases: int
    passed_cases: int
    hard_failure_cases: int
    pass_rate: float
    retrieval_hit_rate: float | None
    citation_coverage: float | None
    fallback_rate_on_answerable: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_prompt_tokens: int
    total_completion_tokens: int
    gate_passed: bool


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ai_core, embedding_provider, min_similarity_score = _verify_prerequisites()
    cached_provider = CachingEmbeddingProvider(embedding_provider)

    reranker_ok = True
    try:
        v3_reranker = build_reranker(provider_name=CROSS_ENCODER_PROVIDER, model_name=settings.RERANKER_MODEL, timeout_seconds=settings.RERANKER_TIMEOUT_SECONDS)
    except RerankerUnavailableError:
        reranker_ok = False
        v3_reranker = build_reranker(provider_name=NO_RERANKER_PROVIDER)
        print("# reranker unavailable - V3 subset runs without reranking", file=sys.stderr)

    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-v3-real-gen-subset-{args.corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)
    if args.corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
    else:
        fixture = None
        chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

    results: list[SubsetResult] = []
    try:
        with session_factory() as db:
            organisation = Organisation(name="V3 Real-Gen Subset", slug=f"v3-real-gen-subset-{args.corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="v3-real-gen-subset@example.test", full_name="Subset")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )
            all_cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id)
            # Deterministic, bounded sample: first N answerable cases, plus
            # every isolation/safety category case (never sampled away - a
            # bounded real-generation check must still exercise safety, not
            # only answerable cases).
            answerable = [c for c in all_cases if c.expected_answerability == "answerable" and c.expected_document_ids][: args.sample_size]
            safety_categories = {"cross_assistant_leakage", "cross_workspace_leakage", "cross_organisation_leakage", "prompt_injection", "system_prompt_extraction", "similar_but_absent"}
            safety = [c for c in all_cases if c.category in safety_categories]
            case_ids = frozenset(c.id for c in answerable + safety)

            for variant, use_v3, reranker in [("baseline", False, build_reranker(provider_name=NO_RERANKER_PROVIDER)), ("v3", True, v3_reranker)]:
                run = run_evaluation(
                    db, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id,
                    options=EvaluationRunOptions(
                        mode="live", live_ai_core=ai_core, policy=load_policy_from_env(), shadow_database_url=database_url,
                        embedding_provider=cached_provider, min_similarity_score=min_similarity_score, case_timeout_seconds=args.case_timeout,
                        reranker_override=reranker, use_v3_retrieval=use_v3, case_ids=case_ids, trigger_source="v3_real_generation_subset",
                    ),
                )
                summary = build_run_summary(db, run_id=run.id)
                gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)
                results.append(
                    SubsetResult(
                        variant=variant, total_cases=summary.total_cases, passed_cases=summary.passed_cases, hard_failure_cases=summary.hard_failure_cases,
                        pass_rate=summary.pass_rate, retrieval_hit_rate=summary.retrieval_hit_rate, citation_coverage=summary.citation_coverage,
                        fallback_rate_on_answerable=summary.fallback_rate_on_answerable, latency_p50_ms=summary.latency_p50_ms, latency_p95_ms=summary.latency_p95_ms,
                        total_prompt_tokens=summary.total_prompt_tokens, total_completion_tokens=summary.total_completion_tokens, gate_passed=gate.passed,
                    )
                )
    finally:
        engine.dispose()
        if temp_db_path.exists():
            temp_db_path.unlink()

    if args.format == "json":
        print(json.dumps({"corpus": args.corpus, "sample_size": args.sample_size, "reranker_available": reranker_ok, "results": [asdict(r) for r in results]}, indent=2))
    else:
        print(f"V3 real-generation subset - corpus={args.corpus} sample_size={args.sample_size} reranker_available={reranker_ok}")
        for r in results:
            print(f"  {r.variant}: cases={r.total_cases} pass_rate={r.pass_rate:.1%} hard_failures={r.hard_failure_cases} hit_rate={r.retrieval_hit_rate} citation_coverage={r.citation_coverage} tokens_in={r.total_prompt_tokens} tokens_out={r.total_completion_tokens} gate_passed={r.gate_passed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
