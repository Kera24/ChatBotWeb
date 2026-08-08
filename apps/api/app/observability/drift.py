from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.observability.metrics import AIObservabilityMetrics, compute_metrics
from app.repositories.observability_repository import TraceFilters

# Deterministic, threshold-based comparisons only - explicitly NOT an ML
# anomaly-detection model, per the observability spec's own instruction.
DEFAULT_DRIFT_THRESHOLD_PCT = 25.0


@dataclass(frozen=True)
class DriftSignal:
    metric: str
    baseline_value: float | None
    current_value: float | None
    absolute_change: float | None
    relative_change_pct: float | None
    threshold_pct: float
    triggered: bool
    direction: str | None


def _relative_change(baseline: float | None, current: float | None) -> float | None:
    if baseline is None or current is None:
        return None
    if baseline == 0:
        return None if current == 0 else 100.0
    return ((current - baseline) / abs(baseline)) * 100.0


def _signal(name: str, baseline: float | None, current: float | None, *, threshold_pct: float) -> DriftSignal:
    change = _relative_change(baseline, current)
    absolute_change = None if (baseline is None or current is None) else current - baseline
    triggered = change is not None and abs(change) >= threshold_pct
    direction = None if change is None else ("up" if change > 0 else "down" if change < 0 else "flat")
    return DriftSignal(
        metric=name, baseline_value=baseline, current_value=current, absolute_change=absolute_change,
        relative_change_pct=change, threshold_pct=threshold_pct, triggered=triggered, direction=direction,
    )


def compute_drift_signals(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    assistant_id: str | None = None,
    now: datetime | None = None,
    threshold_pct: float = DEFAULT_DRIFT_THRESHOLD_PCT,
) -> list[DriftSignal]:
    """Compares the trailing 24h window against the preceding 7-day baseline
    (the 7 days immediately before that 24h window, i.e. excluding it) for a
    fixed set of explainable metrics. Computed on-read (see
    app.observability.metrics.compute_metrics) rather than via a scheduled
    job or materialised snapshot table - acceptable at the pilot scale this
    platform currently targets (see ADR 0018)."""
    now = now or datetime.now(timezone.utc)
    current_start = now - timedelta(hours=24)
    baseline_start = current_start - timedelta(days=7)
    baseline_end = current_start

    current_filters = TraceFilters(
        organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id,
        started_after=current_start, started_before=now,
    )
    baseline_filters = TraceFilters(
        organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id,
        started_after=baseline_start, started_before=baseline_end,
    )
    current = compute_metrics(db, filters=current_filters)
    baseline = compute_metrics(db, filters=baseline_filters)

    baseline_cost_per_request = _cost_per_request(baseline)
    current_cost_per_request = _cost_per_request(current)

    return [
        _signal("fallback_rate", baseline.fallback_rate * 100, current.fallback_rate * 100, threshold_pct=threshold_pct),
        _signal("blocked_rate", baseline.blocked_rate * 100, current.blocked_rate * 100, threshold_pct=threshold_pct),
        _signal("p95_latency_ms", baseline.p95_latency_ms, current.p95_latency_ms, threshold_pct=threshold_pct),
        _signal("cost_per_request", baseline_cost_per_request, current_cost_per_request, threshold_pct=threshold_pct),
        _signal(
            "citation_coverage",
            None if baseline.citation_coverage is None else baseline.citation_coverage * 100,
            None if current.citation_coverage is None else current.citation_coverage * 100,
            threshold_pct=threshold_pct,
        ),
        _signal(
            "evidence_insufficient_rate", baseline.evidence_insufficient_rate * 100, current.evidence_insufficient_rate * 100,
            threshold_pct=threshold_pct,
        ),
        _signal("request_volume", float(baseline.request_volume), float(current.request_volume), threshold_pct=threshold_pct),
    ]


def _cost_per_request(metrics: AIObservabilityMetrics) -> float | None:
    if not metrics.request_volume or metrics.total_estimated_cost is None:
        return None
    return float(metrics.total_estimated_cost) / metrics.request_volume
