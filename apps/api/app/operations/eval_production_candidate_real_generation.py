"""CLI: production-representative end-to-end quality evaluation using the
REAL OpenRouter generation provider (not MockAIProvider) - see
docs/adr/0034-promote-evidence-sufficiency-v2.md's chain of real-embedding
bake-offs, which this task extends one layer further: real GENERATION on
top of the already-validated real-embedding retrieval stack.

Holds the current production candidate configuration fixed (never varies it
within one run - this is a baseline measurement, not a bake-off):
structure_aware chunking, dense_only retrieval, calibrated
nomic-embed-text-v2-moe threshold (0.32, ADR-0032), identity query
transformation, no reranker, Evidence Sufficiency V2 (ADR-0034), the current
citation/guardrail/prompt-management/observability stack unmodified - only
the generation provider changes from mock to real OpenRouter.

    python -m app.operations.eval_production_candidate_real_generation [--format text|json] [--corpus golden|chunking|both] [--keep-db] [--case-timeout 60]

Requires (fails loud, never silently falls back to mock):
- EVAL_EMBEDDING_PROVIDER=ollama, EVAL_EMBEDDING_MODEL set (real embeddings)
- AI_PROVIDER=openrouter, OPENROUTER_API_KEY, OPENROUTER_MODEL set (real
  generation) - verified with one live call before spending on the full
  dataset, since a dead/misconfigured model should fail immediately, not
  after 100+ paid-but-wasted requests.

Captures, per case: actual answer, citations, retrieval/answer metrics
(hit_at_k, recall@k, precision@k, evidence_coverage, citation coverage),
real token usage/latency (OpenRouterAIProvider reports real, non-estimated
usage when the upstream model returns it), and embedding cache stats. For
every FAILED case, additionally re-derives the evidence-sufficiency
verifier's exact reason_code/chunk_outcomes via a second, LLM-free pass
(re-embedding is free - CachingEmbeddingProvider already has every chunk
cached from the main run) - EvaluationResult does not persist a guardrail
reason_code column, so this is the only way to get real-failure taxonomy
detail without a schema change.
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

from app.ai.dependencies import create_ai_core
from app.ai.guardrails.evidence_sufficiency import build_evidence_verifier, verify_evidence_sufficiency_v2
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
from app.evaluation.graders.config import build_real_eval_grader_provider
from app.evaluation.graders.engine import GradingRunStats, grade_result
from app.evaluation.graders.errors import GraderNotConfiguredError
from app.evaluation.graders.rubrics import GraderDimension, advisory_dimensions
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProviderError
from app.services.query_transformation import IdentityQueryTransformer, transform_query
from app.services.reranking import NO_RERANKER_PROVIDER, build_reranker
from app.services.retrieval_context import DENSE_ONLY_STRATEGY, assemble_retrieval_context


@dataclass
class CaseDetail:
    case_id: str
    question: str
    category: str
    tags: list[str]
    expected_answerability: str
    expected_document_ids: list[str]
    passed: bool
    hard_failure: bool
    failure_reasons: list[str]
    answer_state: str | None
    actual_answer: str | None
    retrieved_document_ids: list[str]
    citation_count: int
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    tokens_estimated: bool | None
    retrieval_metrics: dict
    answer_metrics: dict
    # Second-pass, LLM-free re-derivation - only populated for failed cases.
    evidence_reason_code: str | None = None
    evidence_chunk_outcomes: list[str] = field(default_factory=list)
    evidence_hit_at_k: bool | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Production-representative real-generation (OpenRouter) end-to-end evaluation.")
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument("--corpus", default="both", choices=["golden", "chunking", "both"])
    parser.add_argument("--keep-db", action="store_true")
    parser.add_argument("--case-timeout", type=float, default=60.0, help="Per-case timeout in seconds (real network calls - embedding + OpenRouter generation).")
    parser.add_argument(
        "--grade-sample", type=int, default=0,
        help="If > 0, run a REAL (non-mock, Part 8) advisory grader (EVAL_GRADER_PROVIDER/MODEL, e.g. ollama/qwen3.5) on up to this many passed-and-answered "
        "cases plus up to this many failed cases, per corpus, over the already-completed real-generation results (no re-generation, no extra OpenRouter "
        "cost). Advisory dimensions only (app.evaluation.graders.rubrics.advisory_dimensions) - never touches gate/scoring policy. persist=False (the "
        "temp eval DB is discarded either way).",
    )
    return parser.parse_args(argv)


def _verify_prerequisites() -> tuple[object, float]:
    """Fails loud and stops before spending anything on the full dataset if
    either real provider is not genuinely configured/reachable - Part 1's
    explicit requirement."""
    try:
        embedding_provider = build_real_eval_embedding_provider()
    except EmbeddingProviderError as exc:
        print(f"MISSING PREREQUISITE: real embedding provider not available: {exc}", file=sys.stderr)
        raise SystemExit(2)
    recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
    min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE

    if settings.AI_PROVIDER != "openrouter":
        print(f"MISSING PREREQUISITE: AI_PROVIDER={settings.AI_PROVIDER!r}, expected 'openrouter'. Real generation was not configured.", file=sys.stderr)
        raise SystemExit(2)
    if not settings.OPENROUTER_API_KEY:
        print("MISSING PREREQUISITE: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        raise SystemExit(2)
    if not settings.OPENROUTER_MODEL:
        print("MISSING PREREQUISITE: OPENROUTER_MODEL is not set.", file=sys.stderr)
        raise SystemExit(2)

    # One live, minimal call BEFORE the full dataset run - a dead/misnamed
    # model must fail here, not silently degrade the whole run into 139
    # individually-failed cases that could be misread as "the RAG stack is
    # broken" when it's actually "the configured model does not exist".
    from app.ai.service import AICoreGenerateInput

    ai_core = create_ai_core()
    try:
        execution_id = ai_core.accounting_service.create_execution_id()
        response = ai_core.service.generate(
            AICoreGenerateInput(
                prompt_key="grounded_rag_answer", model_key=settings.DEFAULT_AI_MODEL_KEY,
                variables={"question": "Reply with exactly: OK", "context": "No context needed for this check."},
                execution_id=execution_id, organisation_id="prereq-check", workspace_id="prereq-check",
            )
        )
    except Exception as exc:  # noqa: BLE001 - any provider error here is a hard prerequisite failure
        print(f"MISSING PREREQUISITE: real OpenRouter generation call failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
    print(
        f"# prerequisite check passed - real generation confirmed: provider={response.provider_key} model={response.provider_model_name} "
        f"tokens_estimated={response.token_usage.estimated} latency_ms={response.latency_ms}",
        file=sys.stderr,
    )
    return ai_core, min_similarity_score


def _run_grading_sample(db, *, results, cases_by_id: dict, grade_sample: int) -> list[dict]:
    try:
        provider = build_real_eval_grader_provider()
    except GraderNotConfiguredError as exc:
        print(f"# grading skipped - real grader not configured: {exc}", file=sys.stderr)
        return []
    dimensions = advisory_dimensions()
    passed = [r for r in results if r.passed and r.answer_state == "answered"][:grade_sample]
    failed = [r for r in results if not r.passed][:grade_sample]
    stats = GradingRunStats()
    graded: list[dict] = []
    for result in passed + failed:
        case = cases_by_id.get(result.case_id)
        if case is None:
            continue
        outcome = grade_result(db, result=result, case=case, provider=provider, dimensions=dimensions, stats=stats, persist=False)
        graded.append({
            "case_id": case.id, "question": case.question, "passed_deterministic": result.passed,
            "dimensions": {
                dim: (o.result.score if o.result else None, o.result.passed if o.result else None, o.error)
                for dim, o in outcome.dimensions.items()
            },
        })
    print(f"# grading sample - provider={provider.provider_name} model={provider.model_name} graded_cases={stats.graded_cases} errors={stats.errors} total_calls={stats.total_calls}", file=sys.stderr)
    return graded


def _run_corpus(*, corpus: str, ai_core, embedding_provider, min_similarity_score: float, case_timeout: float, keep_db: bool, grade_sample: int = 0):
    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-prod-candidate-real-gen-{corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    cached_provider = CachingEmbeddingProvider(embedding_provider)
    no_reranker = build_reranker(provider_name=NO_RERANKER_PROVIDER)
    identity_transformer = IdentityQueryTransformer()
    evidence_verifier = build_evidence_verifier("v2")
    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)

    if corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
    else:
        fixture = None
        chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

    try:
        with session_factory() as db:
            organisation = Organisation(name="Production Candidate Real Generation Eval", slug=f"prod-candidate-real-gen-{corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="prod-candidate-real-gen@example.test", full_name="Eval")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )
            cases_by_id = {c.id: c for c in evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id)}

            started_at = time.perf_counter()
            run = run_evaluation(
                db, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id,
                options=EvaluationRunOptions(
                    mode="live",
                    live_ai_core=ai_core,
                    policy=load_policy_from_env(),
                    shadow_database_url=database_url,
                    embedding_provider=cached_provider,
                    min_similarity_score=min_similarity_score,
                    case_timeout_seconds=case_timeout,
                    retrieval_strategy_override=DENSE_ONLY_STRATEGY,
                    reranker_override=no_reranker,
                    query_transformer_override=identity_transformer,
                    evidence_verifier_override=evidence_verifier,
                    trigger_source="real_generation_baseline",
                ),
            )
            run_seconds = time.perf_counter() - started_at
            summary = build_run_summary(db, run_id=run.id)
            gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)

            all_results = evaluation_repository.list_results_for_run(db, run_id=run.id)
            details: list[CaseDetail] = []
            for result in all_results:
                case = cases_by_id.get(result.case_id)
                if case is None:
                    continue
                retrieval_metrics = result.retrieval_metrics_json or {}
                answer_metrics = result.answer_metrics_json or {}
                detail = CaseDetail(
                    case_id=case.id, question=case.question, category=case.category, tags=list(case.tags or []),
                    expected_answerability=case.expected_answerability, expected_document_ids=list(case.expected_document_ids or []),
                    passed=bool(result.passed), hard_failure=bool(result.hard_failure), failure_reasons=list(result.failure_reasons_json or []),
                    answer_state=result.answer_state, actual_answer=result.actual_answer,
                    retrieved_document_ids=list(result.retrieved_document_ids or []), citation_count=len(result.citations_json or []),
                    latency_ms=result.latency_ms, input_tokens=result.prompt_tokens, output_tokens=result.completion_tokens,
                    total_tokens=result.total_tokens, tokens_estimated=None,
                    retrieval_metrics=retrieval_metrics, answer_metrics=answer_metrics,
                )

                if not result.passed and case.expected_document_ids and case.expected_answerability == "answerable":
                    # Second, LLM-free pass for real failure taxonomy detail.
                    query_plan = transform_query(identity_transformer, query=case.question)
                    retrieval = assemble_retrieval_context(
                        db, organisation_id=organisation.id, workspace_id=workspace.id, query=case.question,
                        search_limit=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS, max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
                        max_context_chars=settings.RETRIEVAL_MAX_CONTEXT_CHARS, provider=cached_provider, document_ids=None,
                        min_similarity_score=min_similarity_score, retrieval_strategy=DENSE_ONLY_STRATEGY, reranker=no_reranker,
                        query_plan=query_plan,
                    )
                    retrieved_ids = {b.document_id for b in retrieval.context_blocks}
                    detail.evidence_hit_at_k = bool(retrieved_ids & set(case.expected_document_ids))
                    verdict = verify_evidence_sufficiency_v2(
                        question=case.question, chunk_contents=[b.content for b in retrieval.context_blocks],
                        chunk_titles=[b.source_title for b in retrieval.context_blocks], retrieval_scores=[b.score for b in retrieval.context_blocks],
                    )
                    detail.evidence_reason_code = verdict.reason_code.value
                    detail.evidence_chunk_outcomes = list(verdict.chunk_outcomes)

                details.append(detail)

            cache_stats = cached_provider.stats()
            print(f"# corpus={corpus} documents={len(loaded.document_ids)} embedding_cache_stats={cache_stats} run_seconds={run_seconds:.1f}", file=sys.stderr)

            graded_sample: list[dict] = []
            if grade_sample > 0:
                graded_sample = _run_grading_sample(db, results=all_results, cases_by_id=cases_by_id, grade_sample=grade_sample)
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()
    return run, summary, gate, details, cache_stats, run_seconds, graded_sample


def _print_text_report(corpus: str, run, summary, gate, details: list[CaseDetail], cache_stats: dict, run_seconds: float, graded_sample: list[dict]) -> None:
    print(f"=== {corpus} corpus - real generation ({run.provider_key}/{run.provider_model_name}) ===")
    print(f"total={summary.total_cases} passed={summary.passed_cases} failed={summary.failed_cases} hard_failures={summary.hard_failure_cases} pass_rate={summary.pass_rate:.1%}")
    print(f"retrieval_hit_rate={summary.retrieval_hit_rate} recall@k={summary.average_recall_at_k} precision@k={summary.average_precision_at_k}")
    print(f"citation_coverage={summary.citation_coverage} fallback_rate_on_answerable={summary.fallback_rate_on_answerable} correct_fallback_rate_on_unanswerable={summary.correct_fallback_rate_on_unanswerable}")
    print(f"latency p50/p95={summary.latency_p50_ms}/{summary.latency_p95_ms} ms total_tokens={summary.total_tokens}")
    print(f"gate_passed={gate.passed} gate_reasons={list(gate.reasons)}")
    print(f"embedding_cache_stats={cache_stats} run_seconds={run_seconds:.1f}")
    failed = [d for d in details if not d.passed]
    print(f"failed cases: {len(failed)}")
    for d in failed:
        print(f"  [{d.case_id[:8]}] category={d.category} tags={d.tags} reasons={d.failure_reasons} answer_state={d.answer_state}")
        print(f"      evidence_reason_code={d.evidence_reason_code} evidence_hit_at_k={d.evidence_hit_at_k} chunk_outcomes={d.evidence_chunk_outcomes}")
        print(f"      Q: {d.question!r}")
        print(f"      A: {(d.actual_answer or '')[:200]!r}")
    if graded_sample:
        print(f"graded sample ({len(graded_sample)} cases):")
        for g in graded_sample:
            print(f"  [{g['case_id'][:8]}] passed_deterministic={g['passed_deterministic']} {g['question']!r}")
            for dim, (score, passed, error) in g["dimensions"].items():
                if score is None and error is None:
                    continue  # dimension not applicable to this case
                print(f"      {dim}: score={score} passed={passed} error={error}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ai_core, min_similarity_score = _verify_prerequisites()
    embedding_provider = build_real_eval_embedding_provider()

    corpora = ["golden", "chunking"] if args.corpus == "both" else [args.corpus]
    all_output = {}
    for corpus in corpora:
        run, summary, gate, details, cache_stats, run_seconds, graded_sample = _run_corpus(
            corpus=corpus, ai_core=ai_core, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score,
            case_timeout=args.case_timeout, keep_db=args.keep_db, grade_sample=args.grade_sample,
        )
        if args.format == "text":
            _print_text_report(corpus, run, summary, gate, details, cache_stats, run_seconds, graded_sample)
        all_output[corpus] = {
            "run": {"id": run.id, "provider_key": run.provider_key, "model_key": run.model_key, "provider_model_name": run.provider_model_name, "mode": run.mode},
            "summary": asdict(summary) if hasattr(summary, "__dataclass_fields__") else summary.__dict__,
            "gate": {"passed": gate.passed, "reasons": list(gate.reasons)},
            "embedding_cache_stats": cache_stats,
            "run_seconds": run_seconds,
            "cases": [asdict(d) for d in details],
            "graded_sample": graded_sample,
        }

    if args.format == "json":
        print(json.dumps(all_output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
