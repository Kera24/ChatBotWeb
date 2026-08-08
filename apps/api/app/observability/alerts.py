from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.observability.metrics import compute_metrics
from app.operations.logging import log_operational_event
from app.repositories.observability_repository import TraceFilters, count_guardrail_blocks_by_reason

logger = logging.getLogger("chatbotweb.observability.alerts")

# Initial implementation, per the observability spec's own scope: emit
# structured JSON alert events (logged + returned to callers) and expose the
# underlying metrics for external monitoring (Prometheus/Grafana via the VPS
# stack, or Azure Monitor). No webhook/email/paging integration in this pass
# - see docs/06_Operations/AI_Alert_Threshold_Guide.md's deferred-scope note.


@dataclass(frozen=True)
class AlertEvent:
    alert_key: str
    severity: str
    message: str
    metric_value: float | None
    threshold_value: float | None
    triggered_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "alert_key": self.alert_key,
            "severity": self.severity,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "triggered_at": self.triggered_at.isoformat(),
        }


def evaluate_alerts(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    assistant_id: str | None = None,
    window_hours: float = 1.0,
    now: datetime | None = None,
) -> list[AlertEvent]:
    """Deterministic threshold evaluation over a trailing window. Each
    triggered alert is both returned to the caller and emitted as a
    structured JSON log line via log_operational_event - the two lightweight
    delivery mechanisms this pass supports (see module docstring)."""
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)
    filters = TraceFilters(organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id, started_after=window_start, started_before=now)
    metrics = compute_metrics(db, filters=filters)

    events: list[AlertEvent] = []
    sufficient_sample = metrics.request_volume >= settings.AI_ALERT_MIN_SAMPLE_SIZE

    if sufficient_sample and metrics.p95_latency_ms is not None and metrics.p95_latency_ms > settings.AI_ALERT_P95_LATENCY_MS:
        events.append(_event("p95_latency_high", "warning", f"p95 latency {metrics.p95_latency_ms:.0f}ms exceeds threshold {settings.AI_ALERT_P95_LATENCY_MS}ms", metrics.p95_latency_ms, settings.AI_ALERT_P95_LATENCY_MS, now))

    if sufficient_sample and (metrics.provider_failure_rate * 100) > settings.AI_ALERT_PROVIDER_ERROR_RATE_PCT:
        events.append(_event("provider_error_rate_high", "critical", f"Provider error rate {metrics.provider_failure_rate * 100:.1f}% exceeds threshold {settings.AI_ALERT_PROVIDER_ERROR_RATE_PCT}%", metrics.provider_failure_rate * 100, settings.AI_ALERT_PROVIDER_ERROR_RATE_PCT, now))

    if sufficient_sample and (metrics.fallback_rate * 100) > settings.AI_ALERT_FALLBACK_RATE_PCT:
        events.append(_event("fallback_rate_high", "warning", f"Fallback rate {metrics.fallback_rate * 100:.1f}% exceeds threshold {settings.AI_ALERT_FALLBACK_RATE_PCT}%", metrics.fallback_rate * 100, settings.AI_ALERT_FALLBACK_RATE_PCT, now))

    if sufficient_sample and (metrics.evidence_insufficient_rate * 100) > settings.AI_ALERT_EVIDENCE_INSUFFICIENT_RATE_PCT:
        events.append(_event("evidence_insufficient_rate_high", "warning", f"Evidence-insufficient rate {metrics.evidence_insufficient_rate * 100:.1f}% exceeds threshold {settings.AI_ALERT_EVIDENCE_INSUFFICIENT_RATE_PCT}%", metrics.evidence_insufficient_rate * 100, settings.AI_ALERT_EVIDENCE_INSUFFICIENT_RATE_PCT, now))

    if sufficient_sample and (metrics.blocked_rate * 100) > settings.AI_ALERT_GUARDRAIL_BLOCK_RATE_PCT:
        reasons = count_guardrail_blocks_by_reason(db, organisation_id=organisation_id, workspace_id=workspace_id, started_after=window_start, started_before=now)
        top_reason = max(reasons, key=reasons.get) if reasons else "unknown"
        events.append(_event("guardrail_block_rate_high", "warning", f"Guardrail block rate {metrics.blocked_rate * 100:.1f}% exceeds threshold {settings.AI_ALERT_GUARDRAIL_BLOCK_RATE_PCT}% (top reason: {top_reason})", metrics.blocked_rate * 100, settings.AI_ALERT_GUARDRAIL_BLOCK_RATE_PCT, now))

    if settings.AI_ALERT_COST_PER_REQUEST_USD > 0 and metrics.request_volume and metrics.total_estimated_cost is not None:
        cost_per_request = float(metrics.total_estimated_cost) / metrics.request_volume
        if cost_per_request > settings.AI_ALERT_COST_PER_REQUEST_USD:
            events.append(_event("cost_per_request_high", "warning", f"Cost per request ${cost_per_request:.4f} exceeds threshold ${settings.AI_ALERT_COST_PER_REQUEST_USD:.4f}", cost_per_request, settings.AI_ALERT_COST_PER_REQUEST_USD, now))

    zero_traffic_window_start = now - timedelta(minutes=settings.AI_ALERT_ZERO_TRAFFIC_MINUTES)
    zero_traffic_filters = TraceFilters(organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id, started_after=zero_traffic_window_start, started_before=now)
    zero_traffic_metrics = compute_metrics(db, filters=zero_traffic_filters)
    if zero_traffic_metrics.request_volume == 0:
        events.append(_event("zero_traffic", "info", f"No AI requests recorded in the last {settings.AI_ALERT_ZERO_TRAFFIC_MINUTES} minutes", 0, 0, now))

    for event in events:
        log_operational_event(logger, {"event_type": "ai_observability.alert", "organisation_id": organisation_id, "workspace_id": workspace_id, **event.to_dict()})

    return events


def _event(alert_key: str, severity: str, message: str, metric_value: float | None, threshold_value: float | None, now: datetime) -> AlertEvent:
    return AlertEvent(alert_key=alert_key, severity=severity, message=message, metric_value=metric_value, threshold_value=threshold_value, triggered_at=now)
