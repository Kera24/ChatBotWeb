from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Protocol, TypeVar

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.contracts import TokenUsage
from app.ai.model_registry import ModelConfig
from app.core.config import settings
from app.db.models.ai_trace import AIGuardrailTrace, AIModelCallTrace, AIRetrievalTrace, AITrace, AITraceStage
from app.observability.context import AITraceContext
from app.observability.redaction import apply_retention_policy

logger = logging.getLogger("chatbotweb.observability.trace_recorder")

# Bounds how long a single trace write will block a SQLite writer lock held by
# another connection (e.g. the evaluation engine's long-lived session racing
# a ThreadPoolExecutor worker - see app.evaluation.engine) before giving up.
# Deliberately short: SQLite's own busy handler already blocks-and-retries
# internally up to this many milliseconds, so layering additional Python-side
# retries on top would only compound delays. If it still can't get the lock,
# the OperationalError propagates to the caller's own try/except and is
# swallowed there like any other trace-write failure - never surfaced to the
# primary request path. A no-op on Postgres (real production traffic), where
# this class of error does not occur.
_SQLITE_BUSY_TIMEOUT_MS = 3000

_T = TypeVar("_T")


def _run_with_write_session(session_factory: Callable[[], Session], write_fn: Callable[[Session], _T]) -> _T:
    with session_factory() as session:
        try:
            session.execute(text(f"PRAGMA busy_timeout = {_SQLITE_BUSY_TIMEOUT_MS}"))
        except Exception:
            pass  # not SQLite - no-op
        return write_fn(session)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RetrievalTraceEntry:
    rank: int
    selected: bool
    chunk_id: str | None = None
    document_id: str | None = None
    similarity_score: float | None = None
    rejection_reason: str | None = None
    source_title: str | None = None
    content: str | None = None


class AITraceRecorder(Protocol):
    def start_trace(
        self, ctx: AITraceContext, *, organisation_id: str, workspace_id: str, assistant_id: str | None, channel: str
    ) -> None: ...

    def record_stage(
        self,
        ctx: AITraceContext,
        stage_name: str,
        *,
        status: str,
        latency_ms: int | None = None,
        reason_code: str | None = None,
        safe_counts: dict[str, Any] | None = None,
        error_class: str | None = None,
        provider_model_config_version: str | None = None,
    ) -> None: ...

    def record_retrieval(self, ctx: AITraceContext, *, entries: list[RetrievalTraceEntry]) -> None: ...

    def record_model_call(
        self,
        ctx: AITraceContext,
        *,
        model: ModelConfig,
        provider_model_name: str,
        prompt_key: str,
        prompt_version: str | None,
        prompt_hash: str | None,
        token_usage: TokenUsage,
        latency_ms: int,
        finish_reason: str | None,
        outcome: str,
        error_code: str | None = None,
        raw_prompt: str | None = None,
        raw_response: str | None = None,
        attempt_number: int = 1,
        prompt_version_id: str | None = None,
        experiment_id: str | None = None,
        experiment_arm: str | None = None,
        resolved_layer_version_ids: dict[str, str] | None = None,
    ) -> None: ...

    def record_guardrail(
        self,
        ctx: AITraceContext,
        *,
        layer: str,
        guardrail_name: str,
        verdict: str,
        blocked: bool,
        reason_code: str | None = None,
        safe_detail: dict[str, Any] | None = None,
    ) -> None: ...

    def finish_trace(
        self,
        ctx: AITraceContext,
        *,
        status: str,
        answer_state: str | None,
        fallback_used: bool,
        total_latency_ms: int | None,
        provider_key: str | None = None,
        model_key: str | None = None,
        provider_model_name: str | None = None,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        total_tokens: int | None = None,
        estimated_cost: Decimal | None = None,
        error_class: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


class NoOpAITraceRecorder:
    """Zero-overhead default used whenever no recorder is wired in - every
    existing RAGOrchestrator call site that doesn't construct one keeps
    working unchanged (see RAGOrchestratorDependencies.trace_recorder)."""

    def start_trace(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_stage(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_retrieval(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_model_call(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_guardrail(self, *args: Any, **kwargs: Any) -> None:
        return None

    def finish_trace(self, *args: Any, **kwargs: Any) -> None:
        return None


class SqlAlchemyAITraceRecorder:
    """Fail-safe AI trace writer. Uses its own short-lived sessions (never the
    orchestrator's request-scoped `db` session) via `session_factory`, so a
    trace-write failure can never roll back or interfere with conversation
    persistence, and vice versa. Every public method swallows its own
    exceptions - recording AI observability data must never be able to break
    the primary request path.

    Stage/retrieval/guardrail/model-call rows are buffered in memory (one
    recorder instance per request) and flushed in a single commit from
    `finish_trace()`, to keep this to at most two extra DB round trips per
    request. `start_trace()` still writes and commits immediately, so a trace
    row exists even if the request crashes before `finish_trace()` runs.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._trace_row_id: str | None = None
        self._organisation_id: str | None = None
        self._workspace_id: str | None = None
        self._content_mode: str = settings.AI_TRACE_CONTENT_MODE
        self._sequence = 0
        self._pending_stages: list[AITraceStage] = []
        self._pending_retrieval: list[AIRetrievalTrace] = []
        self._pending_guardrails: list[AIGuardrailTrace] = []
        self._pending_model_calls: list[AIModelCallTrace] = []

    def start_trace(
        self, ctx: AITraceContext, *, organisation_id: str, workspace_id: str, assistant_id: str | None, channel: str
    ) -> None:
        try:
            content_mode = settings.AI_TRACE_CONTENT_MODE
            otel_trace_id, otel_span_id = _current_otel_span_ids()
            row = AITrace(
                trace_id=ctx.trace_id,
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                assistant_id=assistant_id,
                conversation_id=ctx.conversation_id,
                request_id=ctx.request_id,
                channel=channel,
                otel_trace_id=otel_trace_id,
                otel_span_id=otel_span_id,
                eval_run_id=ctx.eval_run_id,
                eval_case_id=ctx.eval_case_id,
                status="in_progress",
                content_mode=content_mode,
                created_at=_utc_now(),
            )
            def _write(session: Session) -> str:
                session.add(row)
                session.commit()
                # Must read row.id while still bound to the session:
                # commit() expires attributes by default, and accessing them
                # after the session closes raises DetachedInstanceError.
                return row.id

            trace_row_id = _run_with_write_session(self._session_factory, _write)
            self._trace_row_id = trace_row_id
            self._organisation_id = organisation_id
            self._workspace_id = workspace_id
            self._content_mode = content_mode
        except Exception:
            logger.debug("ai_trace start_trace failed", exc_info=True)
            self._trace_row_id = None

    def record_stage(
        self,
        ctx: AITraceContext,
        stage_name: str,
        *,
        status: str,
        latency_ms: int | None = None,
        reason_code: str | None = None,
        safe_counts: dict[str, Any] | None = None,
        error_class: str | None = None,
        provider_model_config_version: str | None = None,
    ) -> None:
        if self._trace_row_id is None:
            return
        try:
            self._sequence += 1
            self._pending_stages.append(
                AITraceStage(
                    trace_id=self._trace_row_id,
                    organisation_id=self._organisation_id,
                    workspace_id=self._workspace_id,
                    stage_name=stage_name,
                    sequence_number=self._sequence,
                    status=status,
                    latency_ms=latency_ms,
                    reason_code=reason_code,
                    error_class=error_class,
                    safe_counts_json=safe_counts,
                    provider_model_config_version=provider_model_config_version,
                    created_at=_utc_now(),
                )
            )
        except Exception:
            logger.debug("ai_trace record_stage failed", exc_info=True)

    def record_retrieval(self, ctx: AITraceContext, *, entries: list[RetrievalTraceEntry]) -> None:
        if self._trace_row_id is None:
            return
        try:
            for entry in entries:
                preview = apply_retention_policy(entry.content, mode=self._content_mode)
                self._pending_retrieval.append(
                    AIRetrievalTrace(
                        trace_id=self._trace_row_id,
                        organisation_id=self._organisation_id,
                        workspace_id=self._workspace_id,
                        chunk_id=entry.chunk_id,
                        document_id=entry.document_id,
                        rank=entry.rank,
                        similarity_score=(Decimal(str(entry.similarity_score)) if entry.similarity_score is not None else None),
                        selected=entry.selected,
                        rejection_reason=entry.rejection_reason,
                        source_title=entry.source_title,
                        content_preview=preview,
                        created_at=_utc_now(),
                    )
                )
        except Exception:
            logger.debug("ai_trace record_retrieval failed", exc_info=True)

    def record_model_call(
        self,
        ctx: AITraceContext,
        *,
        model: ModelConfig,
        provider_model_name: str,
        prompt_key: str,
        prompt_version: str | None,
        prompt_hash: str | None,
        token_usage: TokenUsage,
        latency_ms: int,
        finish_reason: str | None,
        outcome: str,
        error_code: str | None = None,
        raw_prompt: str | None = None,
        raw_response: str | None = None,
        attempt_number: int = 1,
        prompt_version_id: str | None = None,
        experiment_id: str | None = None,
        experiment_arm: str | None = None,
        resolved_layer_version_ids: dict[str, str] | None = None,
    ) -> None:
        if self._trace_row_id is None:
            return
        try:
            pricing_known = model.input_cost_per_million_tokens is not None and model.output_cost_per_million_tokens is not None
            input_cost = output_cost = total_cost = None
            if pricing_known:
                input_cost = (Decimal(token_usage.input_tokens) / Decimal(1_000_000)) * model.input_cost_per_million_tokens
                output_cost = (Decimal(token_usage.output_tokens) / Decimal(1_000_000)) * model.output_cost_per_million_tokens
                total_cost = input_cost + output_cost
            self._pending_model_calls.append(
                AIModelCallTrace(
                    trace_id=self._trace_row_id,
                    organisation_id=self._organisation_id,
                    workspace_id=self._workspace_id,
                    attempt_number=attempt_number,
                    provider_key=model.provider_key,
                    model_key=model.model_key,
                    provider_model_name=provider_model_name,
                    prompt_key=prompt_key,
                    prompt_version=str(prompt_version) if prompt_version is not None else None,
                    prompt_hash=prompt_hash,
                    input_tokens=token_usage.input_tokens,
                    output_tokens=token_usage.output_tokens,
                    total_tokens=token_usage.total_tokens,
                    estimated_input_cost=input_cost,
                    estimated_output_cost=output_cost,
                    estimated_total_cost=total_cost,
                    cost_calc_version=model.cost_calc_version,
                    pricing_known=pricing_known,
                    latency_ms=latency_ms,
                    finish_reason=finish_reason,
                    outcome=outcome,
                    error_code=error_code,
                    raw_prompt_preview=apply_retention_policy(raw_prompt, mode=self._content_mode),
                    raw_response_preview=apply_retention_policy(raw_response, mode=self._content_mode),
                    # prompt_version_id is the platform_core layer's resolved
                    # PromptVersion id (a quick-filter FK) - the full per-layer
                    # picture (including persona/guidance layers) lives in
                    # resolved_layer_version_ids, since a composite render can
                    # span up to 3 independently-versioned layers and no
                    # single scalar column can represent that (see
                    # docs/architecture/prompts.md's composite-identity
                    # design decision).
                    prompt_version_id=prompt_version_id,
                    experiment_id=experiment_id,
                    experiment_arm=experiment_arm,
                    resolved_layer_version_ids=resolved_layer_version_ids,
                    created_at=_utc_now(),
                )
            )
        except Exception:
            logger.debug("ai_trace record_model_call failed", exc_info=True)

    def record_guardrail(
        self,
        ctx: AITraceContext,
        *,
        layer: str,
        guardrail_name: str,
        verdict: str,
        blocked: bool,
        reason_code: str | None = None,
        safe_detail: dict[str, Any] | None = None,
    ) -> None:
        if self._trace_row_id is None:
            return
        try:
            self._pending_guardrails.append(
                AIGuardrailTrace(
                    trace_id=self._trace_row_id,
                    organisation_id=self._organisation_id,
                    workspace_id=self._workspace_id,
                    layer=layer,
                    guardrail_name=guardrail_name,
                    verdict=verdict,
                    blocked=blocked,
                    reason_code=reason_code,
                    safe_detail_json=safe_detail,
                    created_at=_utc_now(),
                )
            )
        except Exception:
            logger.debug("ai_trace record_guardrail failed", exc_info=True)

    def finish_trace(
        self,
        ctx: AITraceContext,
        *,
        status: str,
        answer_state: str | None,
        fallback_used: bool,
        total_latency_ms: int | None,
        provider_key: str | None = None,
        model_key: str | None = None,
        provider_model_name: str | None = None,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        total_tokens: int | None = None,
        estimated_cost: Decimal | None = None,
        error_class: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._trace_row_id is None:
            return
        try:
            def _write(session: Session) -> None:
                trace_row = session.get(AITrace, self._trace_row_id)
                if trace_row is not None:
                    trace_row.status = status
                    trace_row.answer_state = answer_state
                    trace_row.fallback_used = fallback_used
                    trace_row.total_latency_ms = total_latency_ms
                    trace_row.provider_key = provider_key
                    trace_row.model_key = model_key
                    trace_row.provider_model_name = provider_model_name
                    trace_row.embedding_provider = embedding_provider
                    trace_row.embedding_model = embedding_model
                    trace_row.total_tokens = total_tokens
                    trace_row.estimated_cost = estimated_cost
                    trace_row.error_class = error_class
                    trace_row.metadata_json = metadata
                session.add_all([*self._pending_stages, *self._pending_retrieval, *self._pending_guardrails, *self._pending_model_calls])
                session.commit()

            _run_with_write_session(self._session_factory, _write)
        except Exception:
            logger.debug("ai_trace finish_trace failed", exc_info=True)
        finally:
            self._pending_stages = []
            self._pending_retrieval = []
            self._pending_guardrails = []
            self._pending_model_calls = []


def _current_otel_span_ids() -> tuple[str | None, str | None]:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        span_context = span.get_span_context() if span is not None else None
        if span_context is None or not span_context.is_valid:
            return None, None
        return format(span_context.trace_id, "032x"), format(span_context.span_id, "016x")
    except Exception:
        return None, None
