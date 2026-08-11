"""The evaluation execution engine.

Runs a dataset's cases against one assistant by calling the real,
already-tested `RAGOrchestrator` in-process (see app.ai.rag_orchestrator) -
the exact same code path dashboard/widget traffic uses - rather than
reimplementing retrieval or generation. Each case executes against its own
`shadow_rag_session()` so the ChatSession/ChatMessage/Citation rows the
orchestrator writes are never committed; only the EvaluationRun/Result rows
this module writes through the caller's real `db` session persist.
"""

from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.access.widget_admin.service import WidgetAdminNotFound, get_current_draft, get_widget
from app.ai.dependencies import AICoreContainer, create_ai_core
from app.ai.rag_orchestrator import (
    RAGConversationNotFoundError,
    RAGOrchestrationRequest,
    RAGOrchestrator,
    RAGOrchestratorDependencies,
    RAGProviderExecutionError,
    RAGTenantContextError,
)
from app.core.config import settings
from app.db.models import EvaluationCase, EvaluationDataset, EvaluationRun
from app.evaluation.categories import ISOLATION_CATEGORIES
from app.evaluation.embedding_cache import CachingEmbeddingProvider
from app.observability.ai_trace_recorder import AITraceRecorder, MetricsEmittingAITraceRecorder, NoOpAITraceRecorder
from app.observability.context import AITraceContext, new_trace_id
from app.observability.dependencies import build_ai_trace_recorder
from app.evaluation.metrics.answer import compute_answer_metrics
from app.evaluation.metrics.retrieval import compute_retrieval_metrics
from app.evaluation.policy import DEFAULT_POLICY, EvaluationPolicy
from app.evaluation.redaction import safe_error_message
from app.evaluation.scoring import score_case
from app.evaluation.shadow_session import shadow_rag_session
from app.repositories import evaluation_repository
from app.services.embeddings import EmbeddingProvider, build_embedding_provider

logger = logging.getLogger(__name__)

EvaluationMode = Literal["mock", "live"]

_DEFAULT_CASE_TIMEOUT_SECONDS = 30.0
_DEFAULT_MAX_TOKENS_PER_CASE = 2000


def _build_evaluation_trace_recorder(db: Session) -> AITraceRecorder:
    """AI trace recording for evaluation-triggered RAG calls is skipped on
    SQLite specifically (falls back to a no-op), not because recording is
    unsafe in general, but because of a real, reproduced SQLite-only failure
    mode: `_run_single_case` below executes RAGOrchestrator on a
    ThreadPoolExecutor worker thread while `db` (the caller's long-lived
    session, used for EvaluationRun/EvaluationResult writes across the whole
    run) may still be alive on the main thread. SQLite allows only one writer
    at a time process-wide; a trace-recorder write from the worker thread can
    contend with `db`'s own writes on the main thread badly enough to
    surface "database is locked" errors on `db`'s side too, not just the
    recorder's - i.e. this is one of the few places where a naive recorder
    wiring could actually degrade the primary feature, which the observability
    project's own fail-safety requirement rules out.

    Production evaluation runs use Postgres (proper MVCC, no single-writer
    file lock), where this class of error does not occur - eval-tagged AI
    traces are fully recorded there. SQLite is dev/test-tier only. See
    docs/03_AI/AI_Observability_Architecture.md's limitations section.
    """
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "sqlite":
        # Still wrapped for metrics: MetricsEmittingAITraceRecorder never
        # touches the database itself (see its docstring), so it carries
        # none of the SQLite cross-thread locking risk documented above -
        # only Postgres-writing SqlAlchemyAITraceRecorder does.
        return MetricsEmittingAITraceRecorder(NoOpAITraceRecorder())
    return build_ai_trace_recorder(db)


class EmptyDatasetError(ValueError):
    pass


class LiveModeNotConfiguredError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationRunOptions:
    mode: EvaluationMode = "mock"
    policy: EvaluationPolicy = DEFAULT_POLICY
    case_timeout_seconds: float = _DEFAULT_CASE_TIMEOUT_SECONDS
    max_tokens_per_case: int = _DEFAULT_MAX_TOKENS_PER_CASE
    created_by: str | None = None
    live_ai_core: AICoreContainer | None = None
    shadow_database_url: str | None = None
    category_filter: str | None = None
    # Explicit override so a caller (e.g. a real-embedding evaluation run) can
    # inject a specific embedding provider - most importantly, one that must
    # exactly match whatever provider/model/dimension the dataset's chunks
    # were seeded with - without mutating the global app.core.config settings
    # object, which also governs real customer document embedding.
    embedding_provider: EmbeddingProvider | None = None
    min_similarity_score: float | None = None
    # Restricts the run to an explicit subset of case ids - used by the
    # focused/nightly production-feedback-loop CLI (app.operations.eval_focused_run)
    # to re-run only newly-promoted cases instead of the whole dataset.
    # Independent of category_filter; both apply together if both are set.
    case_ids: frozenset[str] | None = None
    # "manual" (default/None → dashboard-triggered), "nightly", "weekly", or
    # "focused" - set by the scheduled-evaluation CLIs so the dashboard's
    # Scheduled Runs view can distinguish them from ad-hoc runs.
    trigger_source: str | None = None
    # Forces every case's RAGOrchestrationRequest to resolve one specific
    # PromptVersion candidate (see app.prompts.resolution) instead of the
    # widget's normal deployment/experiment assignment - set by
    # app.evaluation.prompt_promotion_gate when gating a candidate before
    # approval/deployment. Resolution raises loudly on any failure to honour
    # this exact version, rather than silently falling back, since the whole
    # point of a gate run is to test this specific candidate.
    prompt_version_override_id: str | None = None
    # Retrieval V2 Phase 1 (docs/future/HybridRetrieval.md) - forces every
    # case's RAGOrchestrationRequest.retrieval_strategy to one specific value
    # ("dense_only"/"hybrid_rrf") instead of the deployment's global
    # settings.RETRIEVAL_STRATEGY, mirroring prompt_version_override_id's
    # exact pattern. Set by the bake-off CLI (app.operations.eval_run
    # --retrieval-strategy) to run the same dataset under both strategies for
    # a controlled comparison; None means "use the global default" for
    # organic runs.
    retrieval_strategy_override: str | None = None
    # Evaluation-performance fix (Retrieval V2 Phase 1 follow-up,
    # app.evaluation.embedding_cache) - memoises embed() by exact
    # (provider, model, dimension, content) so a real-embedding run against
    # SQLite's no-index retrieval path doesn't re-embed every chunk on every
    # case. Defaults on since it is a pure, result-preserving optimisation;
    # exposed as a flag so a test can assert cache-enabled and
    # cache-disabled runs produce byte-identical retrieval results.
    embedding_cache_enabled: bool = True


def run_evaluation(
    db: Session,
    *,
    dataset: EvaluationDataset,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    options: EvaluationRunOptions | None = None,
) -> EvaluationRun:
    options = options or EvaluationRunOptions()
    cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=dataset.id)
    if options.category_filter:
        cases = [case for case in cases if case.category == options.category_filter]
    if options.case_ids is not None:
        cases = [case for case in cases if case.id in options.case_ids]
    if not cases:
        raise EmptyDatasetError(
            f"Dataset {dataset.id} has no cases to run"
            + (f" in category {options.category_filter!r}." if options.category_filter else ".")
            + (f" matching the requested case_ids." if options.case_ids is not None else "")
        )

    if options.mode == "live" and options.live_ai_core is None:
        raise LiveModeNotConfiguredError(
            "Live-provider evaluation requires an explicit ai_core with a real provider registered; "
            "the deterministic mock is used unless one is supplied."
        )
    ai_core = options.live_ai_core if options.mode == "live" else create_ai_core()
    embedding_provider = options.embedding_provider or build_embedding_provider(
        provider_name=settings.EMBEDDING_PROVIDER,
        model_name=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
    )
    # Evaluation-only perf fix (app.evaluation.embedding_cache) - see
    # EvaluationRunOptions.embedding_cache_enabled's docstring. Wraps
    # whatever provider was resolved above (mock or real) transparently;
    # provider_name/model_name/dimension pass through unchanged, so every
    # downstream consumer (retrieval WHERE filters, retrieval_settings below)
    # sees the exact same identity as an unwrapped provider would.
    if options.embedding_cache_enabled:
        embedding_provider = CachingEmbeddingProvider(embedding_provider)
    min_similarity_score = options.min_similarity_score if options.min_similarity_score is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE

    allowed_document_ids = _resolve_allowed_document_ids(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)

    run = evaluation_repository.create_run(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        dataset=dataset,
        mode=options.mode,
        policy_snapshot=options.policy.as_dict(),
        retrieval_settings={
            "retrieval_limit": settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
            "max_context_chars": settings.RETRIEVAL_MAX_CONTEXT_CHARS,
            "min_similarity_score": min_similarity_score,
            "embedding_provider": embedding_provider.provider_name,
            "embedding_model": embedding_provider.model_name,
            "embedding_dimension": embedding_provider.dimension,
            "category_filter": options.category_filter,
            "retrieval_strategy_override": options.retrieval_strategy_override,
        },
        created_by=options.created_by,
        trigger_source=options.trigger_source,
    )
    run = evaluation_repository.mark_run_started(db, run=run)

    total = passed = failed = hard_failures = 0
    provider_key = model_key = provider_model_name = prompt_key = prompt_version = prompt_hash = None

    trace_recorder = _build_evaluation_trace_recorder(db)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        for case in cases:
            outcome = _run_single_case(
                executor,
                case=case,
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                widget_id=widget_id,
                allowed_document_ids=allowed_document_ids,
                ai_core=ai_core,
                embedding_provider=embedding_provider,
                min_similarity_score=min_similarity_score,
                options=options,
                trace_recorder=trace_recorder,
                eval_run_id=run.id,
            )
            evaluation_repository.create_result(db, run_id=run.id, case=case, payload=outcome.payload)
            total += 1
            passed += 1 if outcome.payload["passed"] else 0
            failed += 0 if outcome.payload["passed"] else 1
            hard_failures += 1 if outcome.payload["hard_failure"] else 0
            if outcome.provider_key:
                provider_key, model_key, provider_model_name = outcome.provider_key, outcome.model_key, outcome.provider_model_name
                prompt_key, prompt_version, prompt_hash = outcome.prompt_key, outcome.prompt_version, outcome.prompt_hash

    if isinstance(embedding_provider, CachingEmbeddingProvider):
        run.retrieval_settings_json = {**(run.retrieval_settings_json or {}), **embedding_provider.stats()}
        db.add(run)

    return evaluation_repository.mark_run_completed(
        db,
        run=run,
        status="completed",
        total_cases=total,
        passed_cases=passed,
        failed_cases=failed,
        hard_failure_cases=hard_failures,
        provider_key=provider_key,
        model_key=model_key,
        provider_model_name=provider_model_name,
        prompt_key=prompt_key,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        prompt_version_id=options.prompt_version_override_id,
    )


@dataclass(frozen=True)
class _CaseOutcome:
    payload: dict
    provider_key: str | None = None
    model_key: str | None = None
    provider_model_name: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None


def _run_single_case(
    executor: concurrent.futures.ThreadPoolExecutor,
    *,
    case: EvaluationCase,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    allowed_document_ids: list[str] | None,
    ai_core: AICoreContainer,
    embedding_provider,
    min_similarity_score: float,
    options: EvaluationRunOptions,
    trace_recorder,
    eval_run_id: str,
) -> _CaseOutcome:
    is_isolation_case = case.category in {member.value for member in ISOLATION_CATEGORIES}
    cross_tenant_attempt = (case.metadata_json or {}).get("cross_tenant_attempt") if is_isolation_case else None

    effective_organisation_id = (cross_tenant_attempt or {}).get("organisation_id", organisation_id)
    effective_workspace_id = (cross_tenant_attempt or {}).get("workspace_id", workspace_id)
    effective_widget_id = (cross_tenant_attempt or {}).get("widget_id", widget_id)

    # A fresh trace_id per case, tagged with eval_run_id/eval_case_id so
    # evaluation-triggered RAG calls are distinguishable from real traffic in
    # the AI trace tables (see app.observability.context.AITraceContext -
    # ThreadPoolExecutor workers don't propagate contextvars, so this must be
    # passed explicitly rather than relying on ambient context).
    request = RAGOrchestrationRequest(
        organisation_id=effective_organisation_id,
        workspace_id=effective_workspace_id,
        query=case.question,
        assistant_id=effective_widget_id,
        channel="api",
        min_similarity_score=min_similarity_score,
        trace_context=AITraceContext(trace_id=new_trace_id(), eval_run_id=eval_run_id, eval_case_id=case.id),
        prompt_version_override_id=options.prompt_version_override_id,
        retrieval_strategy=options.retrieval_strategy_override,
    )

    def call() -> object:
        with shadow_rag_session(options.shadow_database_url) as shadow_db:
            orchestrator = RAGOrchestrator(
                RAGOrchestratorDependencies(db=shadow_db, ai_core=ai_core, embedding_provider=embedding_provider, trace_recorder=trace_recorder)
            )
            return orchestrator.answer(request)

    future = executor.submit(call)
    try:
        result = future.result(timeout=options.case_timeout_seconds)
    except concurrent.futures.TimeoutError:
        return _CaseOutcome(payload=_timeout_payload(case, options.case_timeout_seconds))
    except (RAGTenantContextError, RAGConversationNotFoundError) as exc:
        if is_isolation_case:
            # The orchestrator's own tenant checks rejected the cross-tenant
            # attempt cleanly - that is the correct, passing outcome.
            return _CaseOutcome(payload=_isolation_held_payload(case))
        return _CaseOutcome(payload=_unexpected_tenant_error_payload(case, exc))
    except RAGProviderExecutionError as exc:
        return _CaseOutcome(payload=_provider_error_payload(case, exc, allowed_document_ids=allowed_document_ids, options=options))
    except Exception as exc:  # noqa: BLE001 - continue after any unexpected case failure
        logger.exception("Evaluation case %s raised an unexpected error", case.id)
        return _CaseOutcome(payload=_unexpected_error_payload(case, exc))

    cross_tenant_leak_detected = is_isolation_case  # the call above only succeeds for isolation cases if isolation failed
    payload, provider_key, model_key, provider_model_name, prompt_key, prompt_version, prompt_hash = _score_result(
        case,
        result,
        allowed_document_ids=allowed_document_ids,
        cross_tenant_leak_detected=cross_tenant_leak_detected,
        options=options,
    )
    return _CaseOutcome(
        payload=payload,
        provider_key=provider_key,
        model_key=model_key,
        provider_model_name=provider_model_name,
        prompt_key=prompt_key,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
    )


def _score_result(case: EvaluationCase, result, *, allowed_document_ids, cross_tenant_leak_detected: bool, options: EvaluationRunOptions):
    retrieved_document_ids = [citation.document_id for citation in result.citations]
    retrieved_chunk_ids = [citation.chunk_id for citation in result.citations]
    retrieved_source_labels = [citation.source_title for citation in result.citations]
    cited_source_labels = retrieved_source_labels

    retrieval_metrics = compute_retrieval_metrics(
        expected_document_ids=case.expected_document_ids,
        expected_source_labels=case.expected_source_labels,
        retrieved_document_ids=retrieved_document_ids,
        retrieved_chunk_ids=retrieved_chunk_ids,
        retrieved_source_labels=retrieved_source_labels,
        allowed_document_ids=allowed_document_ids if not cross_tenant_leak_detected else None,
        retrieval_strategy=(result.metadata or {}).get("retrieval_strategy"),
        dense_candidate_count=(result.metadata or {}).get("dense_candidate_count"),
        lexical_candidate_count=(result.metadata or {}).get("lexical_candidate_count"),
        fused_candidate_count=(result.metadata or {}).get("fused_candidate_count"),
        dense_latency_ms=(result.metadata or {}).get("dense_latency_ms"),
        lexical_latency_ms=(result.metadata or {}).get("lexical_latency_ms"),
        fusion_latency_ms=(result.metadata or {}).get("fusion_latency_ms"),
    )
    answer_metrics = compute_answer_metrics(
        answer=result.answer,
        answer_state=result.answer_state,
        expected_answerability=case.expected_answerability,
        citation_document_ids=retrieved_document_ids,
        expected_source_labels=case.expected_source_labels,
        cited_source_labels=cited_source_labels,
        retrieved_document_ids=retrieved_document_ids,
        allowed_document_ids=allowed_document_ids,
        latency_ms=result.latency_ms,
        total_tokens=result.token_usage.total_tokens,
        max_latency_ms=options.policy.max_p95_latency_ms,
        max_tokens=options.max_tokens_per_case,
        cross_tenant_leak_detected=cross_tenant_leak_detected,
    )
    score = score_case(
        category=case.category,
        expected_answerability=case.expected_answerability,
        has_expected_documents=bool(case.expected_document_ids),
        has_expected_sources=bool(case.expected_source_labels),
        retrieval=retrieval_metrics,
        answer=answer_metrics,
        citation_required=bool((case.metadata_json or {}).get("citation_required")),
    )

    payload = {
        "actual_answer": result.answer,
        "answer_state": result.answer_state,
        "retrieved_document_ids": retrieved_document_ids,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "citations_json": [
            {
                "document_id": citation.document_id,
                "chunk_id": citation.chunk_id,
                "source_title": citation.source_title,
                "source_type": citation.source_type,
                "similarity_score": citation.similarity_score,
            }
            for citation in result.citations
        ],
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.token_usage.input_tokens,
        "completion_tokens": result.token_usage.output_tokens,
        "total_tokens": result.token_usage.total_tokens,
        "retrieval_metrics_json": retrieval_metrics.as_dict(),
        "answer_metrics_json": answer_metrics.as_dict(),
        "judge_scores_json": None,
        "passed": score.passed,
        "hard_failure": score.hard_failure,
        "failure_reasons_json": score.failure_reasons,
        "error_message": None,
    }
    return payload, result.provider_key, result.model_key, result.provider_model_name, result.prompt_key, result.prompt_version, result.prompt_hash


def _isolation_held_payload(case: EvaluationCase) -> dict:
    return {
        "actual_answer": None,
        "answer_state": None,
        "retrieved_document_ids": [],
        "retrieved_chunk_ids": [],
        "citations_json": [],
        "latency_ms": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "retrieval_metrics_json": None,
        "answer_metrics_json": None,
        "judge_scores_json": None,
        "passed": True,
        "hard_failure": False,
        "failure_reasons_json": [],
        "error_message": None,
    }


def _unexpected_tenant_error_payload(case: EvaluationCase, exc: Exception) -> dict:
    return _failure_payload(safe_error_message(exc), hard_failure=False, reason="unexpected_tenant_context_error")


def _provider_error_payload(case: EvaluationCase, exc: Exception, *, allowed_document_ids, options: EvaluationRunOptions) -> dict:
    # A provider failure on a case that expected an answer is a normal quality
    # failure, not a launch-critical hard failure, unless the case explicitly
    # required a fallback (in which case a "failed" answer_state still counts
    # as a correctly-refused answer).
    reason = "provider_execution_failed"
    payload = _failure_payload(safe_error_message(exc), hard_failure=False, reason=reason)
    payload["answer_state"] = "failed"
    return payload


def _timeout_payload(case: EvaluationCase, timeout_seconds: float) -> dict:
    return _failure_payload(f"Case timed out after {timeout_seconds:.0f}s", hard_failure=False, reason="case_timeout")


def _unexpected_error_payload(case: EvaluationCase, exc: Exception) -> dict:
    return _failure_payload(safe_error_message(exc), hard_failure=False, reason="unexpected_engine_error")


def _failure_payload(error_message: str, *, hard_failure: bool, reason: str) -> dict:
    return {
        "actual_answer": None,
        "answer_state": None,
        "retrieved_document_ids": [],
        "retrieved_chunk_ids": [],
        "citations_json": [],
        "latency_ms": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "retrieval_metrics_json": None,
        "answer_metrics_json": None,
        "judge_scores_json": None,
        "passed": False,
        "hard_failure": hard_failure,
        "failure_reasons_json": [reason],
        "error_message": error_message,
    }


def _resolve_allowed_document_ids(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str) -> list[str] | None:
    try:
        widget = get_widget(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
        draft = get_current_draft(db, widget=widget)
    except WidgetAdminNotFound:
        return None
    scope = list(draft.knowledge_scope_json or [])
    return scope or None
