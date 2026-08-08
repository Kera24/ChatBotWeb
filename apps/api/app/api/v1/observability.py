from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.access.widget_admin.service import WidgetAdminNotFound, get_widget
from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.observability.alerts import evaluate_alerts
from app.observability.drift import compute_drift_signals
from app.observability.metrics import compute_metrics
from app.repositories.observability_repository import TraceFilters, count_traces, get_trace_detail, list_traces
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.observability import (
    AIAlertEventRead,
    AIAnomalySignalRead,
    AIGuardrailTraceRead,
    AIModelCallTraceRead,
    AIObservabilityMetricsRead,
    AIRetrievalTraceRead,
    AITraceDetailRead,
    AITraceStageRead,
    AITraceSummaryRead,
)

router = APIRouter()

MAX_TRACE_LIST_LIMIT = 200

# Base observability data (trace list/detail, metrics, anomalies) follows the
# same viewer-inclusive tier as conversations/analytics - read access, not
# operational configuration.
ObservabilityViewerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]
# Alert events and redacted-content-preview access are restricted to
# org_owner/client_admin, matching the stricter tier used by audit_events.py
# - operationally sensitive, and (for content) may carry customer-typed text
# even after redaction, so viewers should not see it by default.
ObservabilityOperatorDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


@router.get("/{workspace_id}/observability/traces")
def list_workspace_ai_traces(
    workspace_id: str,
    db: DbSession,
    _current_user: ObservabilityViewerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
    assistant_id: str | None = Query(default=None, min_length=1),
    provider_key: str | None = Query(default=None),
    model_key: str | None = Query(default=None),
    answer_state: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    conversation_id: str | None = Query(default=None),
    guardrail_reason_code: str | None = Query(default=None),
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_TRACE_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    assistant = _ensure_assistant(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id) if assistant_id else None
    filters = TraceFilters(
        organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant.id if assistant else None,
        provider_key=provider_key, model_key=model_key, answer_state=answer_state, status=status_filter,
        conversation_id=conversation_id, guardrail_reason_code=guardrail_reason_code,
        started_after=started_after, started_before=started_before,
    )
    rows = list_traces(db, filters=filters, limit=limit, offset=offset)
    total = count_traces(db, filters=filters)
    data = [_summary_read(trace).model_dump(mode="json") for trace in rows]
    return success_response(data, meta={"limit": limit, "offset": offset, "total": total})


@router.get("/{workspace_id}/observability/traces/{trace_id}")
def get_workspace_ai_trace_detail(
    workspace_id: str,
    trace_id: str,
    db: DbSession,
    _current_user: ObservabilityViewerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
    include_content: bool = Query(default=False, description="Include redacted content previews. Requires org_owner/client_admin."),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if include_content and _current_user.role not in {"org_owner", "client_admin", "super_admin"}:
        # Explicit second, stricter role check - FastAPI can't conditionally
        # apply a dependency based on a query parameter declaratively.
        # ObservabilityViewerDependency already re-resolved _current_user.role
        # to the caller's real organisation membership role (or "super_admin"
        # if applicable), so this is a plain comparison, not a re-auth call.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="org_owner or client_admin role required to view trace content previews.")
    detail = get_trace_detail(db, organisation_id=organisation_id, workspace_id=workspace_id, trace_id=trace_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found for workspace.")

    data = AITraceDetailRead(
        summary=_summary_read(detail.trace),
        stages=[
            AITraceStageRead(
                stage_name=stage.stage_name, sequence_number=stage.sequence_number, status=stage.status,
                latency_ms=stage.latency_ms, reason_code=stage.reason_code, error_class=stage.error_class,
                safe_counts=stage.safe_counts_json, provider_model_config_version=stage.provider_model_config_version,
                created_at=stage.created_at,
            )
            for stage in detail.stages
        ],
        retrieval=[
            AIRetrievalTraceRead(
                chunk_id=row.chunk_id, document_id=row.document_id, rank=row.rank, similarity_score=row.similarity_score,
                selected=row.selected, rejection_reason=row.rejection_reason, source_title=row.source_title,
                content_preview=row.content_preview if include_content else None,
            )
            for row in detail.retrieval
        ],
        model_calls=[
            AIModelCallTraceRead(
                attempt_number=call.attempt_number, provider_key=call.provider_key, model_key=call.model_key,
                provider_model_name=call.provider_model_name, prompt_key=call.prompt_key, prompt_version=call.prompt_version,
                prompt_hash=call.prompt_hash, input_tokens=call.input_tokens, output_tokens=call.output_tokens,
                total_tokens=call.total_tokens, estimated_input_cost=call.estimated_input_cost,
                estimated_output_cost=call.estimated_output_cost, estimated_total_cost=call.estimated_total_cost,
                cost_currency=call.cost_currency, cost_calc_version=call.cost_calc_version, pricing_known=call.pricing_known,
                latency_ms=call.latency_ms, finish_reason=call.finish_reason, outcome=call.outcome, error_code=call.error_code,
                raw_prompt_preview=call.raw_prompt_preview if include_content else None,
                raw_response_preview=call.raw_response_preview if include_content else None,
            )
            for call in detail.model_calls
        ],
        guardrails=[
            AIGuardrailTraceRead(
                layer=guardrail.layer, guardrail_name=guardrail.guardrail_name, verdict=guardrail.verdict,
                blocked=guardrail.blocked, reason_code=guardrail.reason_code, safe_detail=guardrail.safe_detail_json,
            )
            for guardrail in detail.guardrails
        ],
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/{workspace_id}/observability/metrics")
def get_workspace_ai_observability_metrics(
    workspace_id: str,
    db: DbSession,
    _current_user: ObservabilityViewerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
    assistant_id: str | None = Query(default=None, min_length=1),
    provider_key: str | None = Query(default=None),
    model_key: str | None = Query(default=None),
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    assistant = _ensure_assistant(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id) if assistant_id else None
    filters = TraceFilters(
        organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant.id if assistant else None,
        provider_key=provider_key, model_key=model_key, started_after=started_after, started_before=started_before,
    )
    metrics = compute_metrics(db, filters=filters)
    data = AIObservabilityMetricsRead(
        request_volume=metrics.request_volume, p50_latency_ms=metrics.p50_latency_ms, p95_latency_ms=metrics.p95_latency_ms,
        total_tokens=metrics.total_tokens, total_estimated_cost=metrics.total_estimated_cost, cost_currency=metrics.cost_currency,
        unknown_cost_request_count=metrics.unknown_cost_request_count, answered_count=metrics.answered_count,
        fallback_count=metrics.fallback_count, blocked_count=metrics.blocked_count, failed_count=metrics.failed_count,
        fallback_rate=metrics.fallback_rate, blocked_rate=metrics.blocked_rate, provider_failure_rate=metrics.provider_failure_rate,
        citation_coverage=metrics.citation_coverage, evidence_insufficient_rate=metrics.evidence_insufficient_rate,
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/{workspace_id}/observability/anomalies")
def get_workspace_ai_observability_anomalies(
    workspace_id: str,
    db: DbSession,
    _current_user: ObservabilityViewerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
    assistant_id: str | None = Query(default=None, min_length=1),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    assistant = _ensure_assistant(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id) if assistant_id else None
    signals = compute_drift_signals(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant.id if assistant else None)
    data = [
        AIAnomalySignalRead(
            metric=signal.metric, baseline_value=signal.baseline_value, current_value=signal.current_value,
            absolute_change=signal.absolute_change, relative_change_pct=signal.relative_change_pct,
            threshold_pct=signal.threshold_pct, triggered=signal.triggered, direction=signal.direction,
        ).model_dump(mode="json")
        for signal in signals
    ]
    return success_response(data)


@router.get("/{workspace_id}/observability/alerts")
def get_workspace_ai_observability_alerts(
    workspace_id: str,
    db: DbSession,
    _current_user: ObservabilityOperatorDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
    assistant_id: str | None = Query(default=None, min_length=1),
    window_hours: float = Query(default=1.0, gt=0, le=24 * 30),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    assistant = _ensure_assistant(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id) if assistant_id else None
    events = evaluate_alerts(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant.id if assistant else None, window_hours=window_hours)
    data = [
        AIAlertEventRead(
            alert_key=event.alert_key, severity=event.severity, message=event.message, metric_value=event.metric_value,
            threshold_value=event.threshold_value, triggered_at=event.triggered_at,
        ).model_dump(mode="json")
        for event in events
    ]
    return success_response(data)


def _summary_read(trace) -> AITraceSummaryRead:  # noqa: ANN001
    return AITraceSummaryRead(
        trace_id=trace.trace_id, organisation_id=trace.organisation_id, workspace_id=trace.workspace_id,
        assistant_id=trace.assistant_id, conversation_id=trace.conversation_id, channel=trace.channel, status=trace.status,
        answer_state=trace.answer_state, fallback_used=trace.fallback_used, total_latency_ms=trace.total_latency_ms,
        provider_key=trace.provider_key, model_key=trace.model_key, total_tokens=trace.total_tokens,
        estimated_cost=trace.estimated_cost, cost_currency=trace.cost_currency, eval_run_id=trace.eval_run_id,
        eval_case_id=trace.eval_case_id, created_at=trace.created_at,
    )


def _ensure_workspace(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


def _ensure_assistant(db: DbSession, *, organisation_id: str, workspace_id: str, assistant_id: str):
    try:
        return get_widget(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=assistant_id)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found for workspace.") from exc
