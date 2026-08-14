"""CLI: Retrieval V2 Phase 3 (docs/future/QueryRewrite.md) controlled
bake-off - dense_only + identity (today's exact production baseline) vs.
dense_only + deterministic vs. dense_only + model_assisted query
transformation, over the SAME corpus, chunking strategy (structure_aware -
ADR-0031), embedding model, calibrated similarity threshold (ADR-0032),
generation provider/prompts/guardrails, and evaluation criteria. Only the
query transformer varies between runs. hybrid_rrf and the reranker are
deliberately NEVER enabled here (Part 11 explicitly excludes them from this
experiment) - every variant runs `RETRIEVAL_STRATEGY=dense_only` with
`RERANKER_PROVIDER=none`. Reuses the existing evaluation framework end to
end (app.evaluation.engine.run_evaluation), the same pattern as
app.operations.eval_reranker_bakeoff - this script adds no new scoring
logic, it seeds the corpus once and re-runs evaluation against it once per
variant.

    python -m app.operations.eval_query_transform_bakeoff [--format text|json] [--real] [--keep-db] [--corpus golden|chunking] [--skip-model-assisted]

Mock mode (default): deterministic, credential-free - proves the mechanics
end-to-end, but LocalMockEmbeddingProvider has no semantic content, so query
transformation cannot show a genuine retrieval-quality signal against it.

`--real`: uses EVAL_EMBEDDING_PROVIDER/EVAL_EMBEDDING_MODEL (must already be
set, e.g. ollama/nomic-embed-text-v2-moe) for a genuinely semantically
meaningful comparison, and applies this project's calibrated
RETRIEVAL_MIN_SIMILARITY_SCORE for that model (0.32 for
nomic-embed-text-v2-moe, docs/adr/0032) - the threshold itself is never
varied by this script.

Variants compared:
  identity        - the current production baseline, transformation disabled
                     (one retrieval query: the original question, unchanged).
  deterministic   - local, LLM-free normalization (conversational-filler
                     stripping + whole-word abbreviation expansion).
  model_assisted  - a concise, search-oriented reformulation. Per this
                     project's known constraint (no live OpenAI/Anthropic/
                     Azure OpenAI provider is wired in - see CLAUDE.md), and
                     per this task's explicit "do NOT introduce another paid
                     provider" instruction, this arm reuses the EXISTING
                     `app.ai.providers.openrouter.OpenRouterAIProvider` class
                     unmodified, pointed at a local Ollama instance's
                     OpenAI-compatible endpoint (default
                     http://localhost:11434/v1) instead of the real
                     OpenRouter API - a genuine local LLM call, zero cost, no
                     external network, no credentials. Skipped automatically
                     (with a clear message, not a silent no-op) if that local
                     endpoint is unreachable - see `--skip-model-assisted` to
                     do this explicitly. The main RAG answer-generation step
                     for every variant (including this one) stays on the mock
                     provider throughout, per Part 11's "keep generation
                     configuration constant" requirement - only the query
                     REWRITE call for this one arm uses a real local model.

Also computes, per case, the Part 12 "query rescue rate" / "query damage
rate" and Part 13 case-level mechanism classification by diffing each
candidate variant's per-case `hit_at_k` against the identity baseline's, for
every answerable_factual case that declares expected_document_ids.

Exits 0 regardless of any individual variant's gate result (this is a
comparison report, not a pass/fail gate) - see the printed promotion check
for the actual accept/reject call (Part 14 policy).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ai.accounting import AIUsageAccountingRepository, AIUsageAccountingService
from app.ai.dependencies import AICoreContainer, build_query_rewrite_generate_fn
from app.ai.execution_policy import ProviderExecutionPolicy
from app.ai.executor import ProviderRetryExecutor
from app.ai.health import ProviderHealthService
from app.ai.model_registry import ModelConfig, ModelRegistry
from app.ai.prompt_registry import PromptRegistry, register_default_query_rewrite_prompt
from app.ai.provider_registry import ProviderRegistry
from app.ai.providers.openrouter import OpenRouterAIProvider
from app.ai.service import AICoreService
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
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider
from app.services.query_transformation import (
    DETERMINISTIC_PROVIDER,
    IDENTITY_PROVIDER,
    MODEL_ASSISTED_PROVIDER,
    QueryTransformer,
    build_query_transformer,
    transform_query,
)
from app.services.reranking import NO_RERANKER_PROVIDER, build_reranker
from app.services.retrieval_context import DENSE_ONLY_STRATEGY

DEFAULT_LOCAL_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_LOCAL_OLLAMA_MODEL = "qwen3.5:latest"

# Reproduced from app.operations.eval_query_failure_analysis deliberately
# (not imported) - this script's mechanism classification must stay a fixed
# reference vocabulary of its own, independent of whatever the transformer's
# internal normalisation list evolves to.
_CONVERSATIONAL_PREFIXES = [
    r"^can you (please )?tell me\s+",
    r"^could you (please )?(explain|tell me)\s+",
    r"^i (want|need|would like) to know\s+",
    r"^i'?m (trying to find out|wondering)\s+",
    r"^do you know\s+",
    r"^please (tell me|explain)\s+",
    r"^what about\s+",
    r"^how do i\s+",
]


@dataclass(frozen=True)
class Variant:
    label: str
    transformer: QueryTransformer


@dataclass
class VariantResult:
    label: str
    query_transformer_provider: str
    query_transformer_model: str
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
    # Query-transformation-specific telemetry (Part 12), computed by calling
    # transform_query directly on every case question - independent of
    # run_evaluation/persisted EvaluationResult rows, which (like reranker
    # debug info before it) do not carry query-transformer fields into
    # storage, only into transient RAGOrchestrationResult.metadata/OTel.
    average_generated_query_count: float = 1.0
    average_transform_latency_ms: float = 0.0
    transform_status_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class CaseTransition:
    variant_label: str
    case_id: str
    question: str
    category: str
    baseline_hit: bool | None
    candidate_hit: bool | None
    baseline_reciprocal_rank: float | None
    candidate_reciprocal_rank: float | None
    candidate_status: str
    candidate_retrieval_queries: list[str]
    candidate_answer_state: str | None
    candidate_failure_reasons: list[str]
    mechanism: str
    direction: str  # "rescued" | "damaged"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled bake-off: dense_only identity baseline vs. deterministic vs. model_assisted query transformation.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--real", action="store_true", help="Use EVAL_EMBEDDING_PROVIDER/MODEL (a real embedding runtime) instead of the deterministic mock.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the temp SQLite file afterwards.")
    parser.add_argument(
        "--corpus", default="golden", choices=["golden", "chunking"],
        help="'golden' (default): golden_dataset.json, the general launch/regression corpus. "
        "'chunking': chunking_dataset.json, the structurally-rich corpus purpose-built for the retrieval-recall gap (104 cases).",
    )
    parser.add_argument("--skip-model-assisted", action="store_true", help="Only compare identity vs deterministic (skip the model_assisted arm entirely).")
    parser.add_argument("--ollama-base-url", default=DEFAULT_LOCAL_OLLAMA_BASE_URL, help="Local Ollama OpenAI-compatible endpoint used for the model_assisted arm's rewrite calls (never a paid provider).")
    parser.add_argument("--ollama-model", default=DEFAULT_LOCAL_OLLAMA_MODEL, help="Local Ollama chat model used for the model_assisted arm's rewrite calls.")
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
    return build_embedding_provider(provider_name="local-mock", model_name="query-transform-bakeoff", dimension=8), settings.RETRIEVAL_MIN_SIMILARITY_SCORE


def _local_ollama_reachable(base_url: str) -> bool:
    try:
        # Ollama's OpenAI-compatible surface has no unauthenticated /models
        # probe guarantee across versions - a bare GET to the host root is
        # enough to prove "something is listening here" without depending on
        # any one specific endpoint shape.
        host_root = base_url.split("/v1", 1)[0] or base_url
        response = httpx.get(host_root, timeout=2.0)
        return response.status_code < 500
    except httpx.HTTPError:
        return False


def _build_local_model_assisted_transformer(*, base_url: str, model: str, timeout_seconds: float, max_query_chars: int, max_queries: int) -> QueryTransformer:
    """Builds a fully independent AICoreService (own provider/model/prompt
    registries) whose sole purpose is answering this variant's query-rewrite
    calls against a LOCAL Ollama model via the existing
    `OpenRouterAIProvider` class pointed at Ollama's OpenAI-compatible
    endpoint - never touching the shared `create_ai_core()` container
    `run_evaluation` builds per-run (which only has the mock/production
    provider registered), and never making a real OpenRouter network call.
    The main RAG answer-generation step keeps using the mock provider
    exactly as every other variant does - only this transformer's own
    rewrite call is routed here."""
    provider_registry = ProviderRegistry()
    provider_registry.register(
        OpenRouterAIProvider(api_key="unused-local-ollama", model=model, base_url=base_url, temperature=0.0, max_output_tokens=300, timeout_seconds=timeout_seconds)
    )
    model_registry = ModelRegistry(provider_registry)
    model_key = "query_rewrite_local_ollama"
    model_registry.register(
        ModelConfig(model_key=model_key, provider_key="openrouter", provider_model_name=model, display_name=f"Local Ollama: {model}", enabled=True, context_window=32_000)
    )
    prompt_registry = PromptRegistry()
    register_default_query_rewrite_prompt(prompt_registry)
    accounting_repository = AIUsageAccountingRepository()
    accounting_service = AIUsageAccountingService(accounting_repository)
    health_service = ProviderHealthService(provider_registry)
    retry_executor = ProviderRetryExecutor()
    execution_policy = ProviderExecutionPolicy(timeout_seconds=timeout_seconds)
    service = AICoreService(
        provider_registry=provider_registry, model_registry=model_registry, prompt_registry=prompt_registry,
        accounting_service=accounting_service, health_service=health_service, retry_executor=retry_executor, execution_policy=execution_policy,
    )
    ai_core = AICoreContainer(
        provider_registry=provider_registry, model_registry=model_registry, prompt_registry=prompt_registry,
        accounting_repository=accounting_repository, accounting_service=accounting_service, health_service=health_service,
        retry_executor=retry_executor, execution_policy=execution_policy, service=service,
    )
    generate_fn = build_query_rewrite_generate_fn(ai_core, model_key=model_key)
    return build_query_transformer(
        provider_name=MODEL_ASSISTED_PROVIDER, model_name=model_key, timeout_seconds=timeout_seconds,
        generate_fn=generate_fn, max_query_chars=max_query_chars, max_queries=max_queries,
    )


def _is_conversational(question: str) -> bool:
    return any(re.match(pattern, question, flags=re.IGNORECASE) for pattern in _CONVERSATIONAL_PREFIXES)


def _classify_transition_mechanism(*, question: str, plan_status: str, retrieval_queries: list[str], direction: str) -> str:
    """Deterministic, evidence-based classification (Part 13) - never
    guesses a mechanism the transformer's own output doesn't support.
    Inspects the actual RetrievalQueryPlan produced for this case (status +
    the retrieval queries it generated), not the case outcome alone."""
    if plan_status in {"failed", "timeout", "malformed_output", "unavailable"}:
        return "transformer_failure_safe_fallback"
    if plan_status in {"identity", "unchanged"} or len(retrieval_queries) <= 1:
        return "unrelated_noise_no_query_change"

    rewritten = " ".join(retrieval_queries[1:]).lower()
    question_lower = question.lower()
    if _is_conversational(question) and not _is_conversational(rewritten):
        return "conversational_to_canonical_wording"

    question_words = set(re.findall(r"[a-z0-9]+", question_lower))
    rewritten_words = set(re.findall(r"[a-z0-9]+", rewritten))
    new_words = rewritten_words - question_words
    if new_words:
        return "terminology_mismatch_fixed" if direction == "rescued" else "query_dilution"

    if len(retrieval_queries) > 2:
        return "competing_document_promotion" if direction == "damaged" else "unclassified_needs_manual_review"

    return "unclassified_needs_manual_review"


def _run_all_variants(
    variants: list[Variant], *, embedding_provider: EmbeddingProvider, min_similarity_score: float, keep_db: bool, corpus: str,
) -> tuple[list[VariantResult], list[CaseTransition]]:
    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-query-transform-bakeoff-{corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    cached_provider = CachingEmbeddingProvider(embedding_provider)
    no_reranker = build_reranker(provider_name=NO_RERANKER_PROVIDER)

    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)
    if corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
    else:
        fixture = None
        chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

    results: list[VariantResult] = []
    run_ids_by_label: dict[str, str] = {}
    try:
        with session_factory() as db:
            organisation = Organisation(name="Query Transform Bakeoff", slug=f"query-transform-bakeoff-{corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="query-transform-bakeoff@example.test", full_name="Bakeoff")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )
            chunk_count = len(db.execute(select(Chunk).where(Chunk.organisation_id == organisation.id)).scalars().all())
            cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id)

            for variant in variants:
                # Independent of run_evaluation - the direct, per-case
                # transform_query pass this bake-off needs for Part 12
                # aggregate latency/query-count telemetry and Part 13
                # case-level query-plan detail (neither is persisted onto
                # EvaluationResult, matching the reranker bake-off's
                # equivalent pre-existing limitation for its own debug info).
                plans_by_case_id = {case.id: transform_query(variant.transformer, query=case.question, fail_loud=False) for case in cases}

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
                        retrieval_strategy_override=DENSE_ONLY_STRATEGY,
                        reranker_override=no_reranker,
                        query_transformer_override=variant.transformer,
                    ),
                )
                run_seconds = time.perf_counter() - started_at
                run_ids_by_label[variant.label] = run.id
                summary = build_run_summary(db, run_id=run.id)
                gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)
                failure_reason_counts = _failure_reason_counts(db, run_id=run.id)

                statuses = [plan.status for plan in plans_by_case_id.values()]
                status_counts: dict[str, int] = {}
                for status in statuses:
                    status_counts[status] = status_counts.get(status, 0) + 1
                avg_query_count = sum(len(plan.retrieval_queries) for plan in plans_by_case_id.values()) / len(plans_by_case_id) if plans_by_case_id else 1.0
                avg_latency = sum(plan.latency_ms for plan in plans_by_case_id.values()) / len(plans_by_case_id) if plans_by_case_id else 0.0

                results.append(
                    VariantResult(
                        label=variant.label,
                        query_transformer_provider=variant.transformer.provider_name,
                        query_transformer_model=variant.transformer.model_name,
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
                        average_generated_query_count=avg_query_count,
                        average_transform_latency_ms=avg_latency,
                        transform_status_counts=status_counts,
                    )
                )
            print(f"# corpus documents={len(loaded.document_ids)} chunks={chunk_count} cache_stats={cached_provider.stats()}", flush=True)

            transitions = _compute_transitions(db, run_ids_by_label=run_ids_by_label, cases=cases, variants=variants)
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()
    return results, transitions


def _compute_transitions(db, *, run_ids_by_label: dict[str, str], cases: list, variants: list[Variant]) -> list[CaseTransition]:
    baseline_label = variants[0].label
    if baseline_label not in run_ids_by_label:
        return []
    baseline_results = {r.case_id: r for r in evaluation_repository.list_results_for_run(db, run_id=run_ids_by_label[baseline_label])}
    cases_by_id = {case.id: case for case in cases}

    transitions: list[CaseTransition] = []
    for variant in variants[1:]:
        run_id = run_ids_by_label.get(variant.label)
        if run_id is None:
            continue
        candidate_results = {r.case_id: r for r in evaluation_repository.list_results_for_run(db, run_id=run_id)}
        for case_id, baseline_result in baseline_results.items():
            case = cases_by_id.get(case_id)
            if case is None or not case.expected_document_ids or case.expected_answerability != "answerable":
                continue
            candidate_result = candidate_results.get(case_id)
            if candidate_result is None:
                continue
            baseline_metrics = baseline_result.retrieval_metrics_json or {}
            candidate_metrics = candidate_result.retrieval_metrics_json or {}
            baseline_hit = baseline_metrics.get("hit_at_k")
            candidate_hit = candidate_metrics.get("hit_at_k")
            # A None on either side means that case didn't run to a normal
            # retrieval-scored completion at all (e.g. the candidate hard-
            # failed with reason="query_transformer_failed" under this
            # bake-off's fail_loud=True evaluation policy, or an unrelated
            # engine error) - that is a distinct outcome from "retrieval
            # regressed", and must never be silently folded into the damage
            # count (None is falsy, so `not baseline_hit and candidate_hit`
            # would otherwise misclassify every such case as "damaged").
            if baseline_hit is None or candidate_hit is None or baseline_hit == candidate_hit:
                continue  # not a boolean-comparable rescue/damage transition

            direction = "rescued" if (not baseline_hit and candidate_hit) else "damaged"
            plan = transform_query(variant.transformer, query=case.question, fail_loud=False)
            transitions.append(
                CaseTransition(
                    variant_label=variant.label,
                    case_id=case_id,
                    question=case.question,
                    category=case.category,
                    baseline_hit=baseline_hit,
                    candidate_hit=candidate_hit,
                    baseline_reciprocal_rank=baseline_metrics.get("reciprocal_rank"),
                    candidate_reciprocal_rank=candidate_metrics.get("reciprocal_rank"),
                    candidate_status=plan.status,
                    candidate_retrieval_queries=list(plan.retrieval_queries),
                    candidate_answer_state=candidate_result.answer_state,
                    candidate_failure_reasons=list(candidate_result.failure_reasons_json or []),
                    mechanism=_classify_transition_mechanism(
                        question=case.question, plan_status=plan.status, retrieval_queries=list(plan.retrieval_queries), direction=direction,
                    ),
                    direction=direction,
                )
            )
    return transitions


def _failure_reason_counts(db, *, run_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in evaluation_repository.list_results_for_run(db, run_id=run_id):
        for reason in result.failure_reasons_json or []:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _print_text_report(results: list[VariantResult], transitions: list[CaseTransition], *, embedding_provider: EmbeddingProvider, min_similarity_score: float, corpus: str) -> None:
    print(
        f"Retrieval V2 Phase 3 query-transformation bake-off - corpus: {corpus} - embedding provider: "
        f"{embedding_provider.provider_name}/{embedding_provider.model_name} - min_similarity_score: {min_similarity_score}"
    )
    print()
    header = (
        f"{'variant':16s} {'pass_rate':>9s} {'hard_fail':>9s} {'hit_rate':>9s} {'recall@k':>9s} {'precision@k':>11s} "
        f"{'citation':>9s} {'fallback':>9s} {'p50/p95 ms':>12s} {'tokens':>8s} {'avg_q':>6s} {'xform_ms':>9s} {'run_s':>7s} {'gate':>7s}"
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
            f"{r.label:16s} {r.pass_rate:8.1%} {r.hard_failure_cases:9d} {hit_rate:>9s} {recall:>9s} {precision:>11s} "
            f"{citation:>9s} {fallback:>9s} {latency:>12s} {r.total_tokens:8d} {r.average_generated_query_count:6.2f} "
            f"{r.average_transform_latency_ms:9.1f} {r.run_seconds:7.1f} {'PASS' if r.gate_passed else 'FAIL':>7s}"
        )
        print(f"    transform_status_counts: {r.transform_status_counts}")
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

        this_candidate_transitions = [t for t in transitions if t.variant_label == candidate.label]
        rescued = [t for t in this_candidate_transitions if t.direction == "rescued"]
        damaged = [t for t in this_candidate_transitions if t.direction == "damaged"]
        print(f"  QUERY RESCUE RATE: {len(rescued)} case(s) newly retrieve expected evidence")
        print(f"  QUERY DAMAGE RATE: {len(damaged)} case(s) newly fail to retrieve expected evidence")
        for t in rescued:
            print(f"    [RESCUED] ({t.mechanism}) {t.question!r}")
            print(f"        retrieval_queries={t.candidate_retrieval_queries} rr_before={t.baseline_reciprocal_rank} rr_after={t.candidate_reciprocal_rank} answer_state={t.candidate_answer_state}")
        for t in damaged:
            print(f"    [DAMAGED] ({t.mechanism}) {t.question!r}")
            print(f"        retrieval_queries={t.candidate_retrieval_queries} rr_before={t.baseline_reciprocal_rank} rr_after={t.candidate_reciprocal_rank} answer_state={t.candidate_answer_state} failure_reasons={t.candidate_failure_reasons}")

        # Part 14 promotion policy (necessary, not sufficient - human
        # case-level judgement over the rescued/damaged lists above is still
        # required): zero new hard failures, citation integrity maintained,
        # pass rate non-regressive, recall@k materially improves, damage rate
        # very low relative to rescue rate.
        non_regressive = (
            new_hard_failures <= 0
            and pass_rate_delta >= -0.001
            and (citation_delta is None or citation_delta >= -0.001)
        )
        recall_materially_improved = recall_delta is not None and recall_delta >= 0.02
        damage_acceptable = len(damaged) <= max(1, len(rescued) // 4)
        print(
            f"  Part 14 promotion check: {'non-regressive' if non_regressive else 'REGRESSION'}, "
            f"recall materially improved: {recall_materially_improved}, damage rate acceptable relative to rescue: {damage_acceptable}"
        )
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

    variants = [
        Variant(label="identity", transformer=build_query_transformer(provider_name=IDENTITY_PROVIDER)),
        Variant(label="deterministic", transformer=build_query_transformer(provider_name=DETERMINISTIC_PROVIDER, max_queries=settings.QUERY_TRANSFORMER_MAX_QUERIES)),
    ]
    if not args.skip_model_assisted:
        if _local_ollama_reachable(args.ollama_base_url):
            variants.append(
                Variant(
                    label="model_assisted",
                    transformer=_build_local_model_assisted_transformer(
                        base_url=args.ollama_base_url, model=args.ollama_model,
                        timeout_seconds=settings.QUERY_TRANSFORMER_TIMEOUT_SECONDS,
                        max_query_chars=settings.QUERY_TRANSFORMER_MAX_QUERY_CHARS,
                        max_queries=settings.QUERY_TRANSFORMER_MAX_QUERIES,
                    ),
                )
            )
        else:
            print(
                f"# model_assisted arm skipped - local Ollama endpoint {args.ollama_base_url!r} unreachable. "
                "Start Ollama locally (or pass --ollama-base-url) to include this arm; per CLAUDE.md's known "
                "constraint ('no live OpenAI/Anthropic/Azure OpenAI provider is wired in yet') and this task's "
                "'do NOT introduce another paid provider' instruction, this script never falls back to a real "
                "paid API for this arm.",
                flush=True,
            )

    results, transitions = _run_all_variants(
        variants, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score, keep_db=args.keep_db, corpus=args.corpus,
    )

    if args.format == "json":
        print(
            json.dumps(
                {
                    "corpus": args.corpus,
                    "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name},
                    "min_similarity_score": min_similarity_score,
                    "results": [asdict(r) for r in results],
                    "transitions": [asdict(t) for t in transitions],
                },
                indent=2, default=str,
            )
        )
    else:
        _print_text_report(results, transitions, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score, corpus=args.corpus)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
