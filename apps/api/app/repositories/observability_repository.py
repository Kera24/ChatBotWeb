from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session

from app.db.models.ai_trace import AIGuardrailTrace, AIModelCallTrace, AIRetrievalTrace, AITrace, AITraceStage

MAX_TRACE_LIST_LIMIT = 200


@dataclass(frozen=True)
class TraceFilters:
    organisation_id: str
    workspace_id: str
    assistant_id: str | None = None
    provider_key: str | None = None
    model_key: str | None = None
    answer_state: str | None = None
    status: str | None = None
    conversation_id: str | None = None
    guardrail_reason_code: str | None = None
    started_after: datetime | None = None
    started_before: datetime | None = None


@dataclass(frozen=True)
class TraceDetail:
    trace: AITrace
    stages: list[AITraceStage]
    retrieval: list[AIRetrievalTrace]
    model_calls: list[AIModelCallTrace]
    guardrails: list[AIGuardrailTrace]


def _apply_filters(statement: Select, filters: TraceFilters) -> Select:
    statement = statement.where(
        AITrace.organisation_id == filters.organisation_id,
        AITrace.workspace_id == filters.workspace_id,
    )
    if filters.assistant_id is not None:
        statement = statement.where(AITrace.assistant_id == filters.assistant_id)
    if filters.provider_key is not None:
        statement = statement.where(AITrace.provider_key == filters.provider_key)
    if filters.model_key is not None:
        statement = statement.where(AITrace.model_key == filters.model_key)
    if filters.answer_state is not None:
        statement = statement.where(AITrace.answer_state == filters.answer_state)
    if filters.status is not None:
        statement = statement.where(AITrace.status == filters.status)
    if filters.conversation_id is not None:
        statement = statement.where(AITrace.conversation_id == filters.conversation_id)
    if filters.started_after is not None:
        statement = statement.where(AITrace.created_at >= filters.started_after)
    if filters.started_before is not None:
        statement = statement.where(AITrace.created_at <= filters.started_before)
    if filters.guardrail_reason_code is not None:
        matching_trace_ids = select(AIGuardrailTrace.trace_id).where(AIGuardrailTrace.reason_code == filters.guardrail_reason_code)
        statement = statement.where(AITrace.id.in_(matching_trace_ids))
    return statement


def list_traces(db: Session, *, filters: TraceFilters, limit: int = 50, offset: int = 0) -> list[AITrace]:
    safe_limit = max(1, min(limit, MAX_TRACE_LIST_LIMIT))
    statement = _apply_filters(select(AITrace), filters).order_by(AITrace.created_at.desc()).limit(safe_limit).offset(max(0, offset))
    return list(db.execute(statement).scalars().all())


def count_traces(db: Session, *, filters: TraceFilters) -> int:
    from sqlalchemy import func

    statement = _apply_filters(select(func.count(AITrace.id)), filters)
    return int(db.execute(statement).scalar_one())


def get_trace_detail(db: Session, *, organisation_id: str, workspace_id: str, trace_id: str) -> TraceDetail | None:
    trace = db.execute(
        select(AITrace).where(
            AITrace.trace_id == trace_id,
            AITrace.organisation_id == organisation_id,
            AITrace.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if trace is None:
        return None
    stages = list(
        db.execute(select(AITraceStage).where(AITraceStage.trace_id == trace.id).order_by(AITraceStage.sequence_number)).scalars().all()
    )
    retrieval = list(
        db.execute(select(AIRetrievalTrace).where(AIRetrievalTrace.trace_id == trace.id).order_by(AIRetrievalTrace.rank)).scalars().all()
    )
    model_calls = list(
        db.execute(select(AIModelCallTrace).where(AIModelCallTrace.trace_id == trace.id).order_by(AIModelCallTrace.attempt_number)).scalars().all()
    )
    guardrails = list(
        db.execute(select(AIGuardrailTrace).where(AIGuardrailTrace.trace_id == trace.id).order_by(AIGuardrailTrace.created_at)).scalars().all()
    )
    return TraceDetail(trace=trace, stages=stages, retrieval=retrieval, model_calls=model_calls, guardrails=guardrails)


def list_traces_for_metrics(db: Session, *, filters: TraceFilters) -> list[AITrace]:
    """Unpaginated fetch used by aggregate-metrics/anomaly computation. Bounded
    implicitly by the caller's date-range filter; at pilot scale (see ADR
    0018) an on-read Python aggregation is fast enough without a materialised
    rollup table (see docs/.../AI_Observability_Architecture.md)."""
    statement = _apply_filters(select(AITrace), filters).order_by(AITrace.created_at.desc())
    return list(db.execute(statement).scalars().all())


def count_guardrail_blocks_by_reason(db: Session, *, organisation_id: str, workspace_id: str, started_after: datetime | None, started_before: datetime | None) -> dict[str, int]:
    from sqlalchemy import func

    statement = (
        select(AIGuardrailTrace.reason_code, func.count(AIGuardrailTrace.id))
        .where(
            AIGuardrailTrace.organisation_id == organisation_id,
            AIGuardrailTrace.workspace_id == workspace_id,
            AIGuardrailTrace.blocked.is_(True),
        )
        .group_by(AIGuardrailTrace.reason_code)
    )
    if started_after is not None:
        statement = statement.where(AIGuardrailTrace.created_at >= started_after)
    if started_before is not None:
        statement = statement.where(AIGuardrailTrace.created_at <= started_before)
    rows = db.execute(statement).all()
    return {(reason_code or "unknown"): count for reason_code, count in rows}
