"""Pure aggregation functions for the production feedback loop's metrics
section (spec section 11). Each function takes the caller's `db` session and
returns plain Python data - no framework/response-shape concerns here, that's
`app.api.v1.evaluation_candidates`'s job.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationCandidate, EvaluationDatasetVersionEvent, EvaluationResult


@dataclass(frozen=True)
class FeedbackLoopMetrics:
    candidates_by_status: dict[str, int]
    candidates_by_signal_type: dict[str, int]
    candidates_by_severity: dict[str, int]
    failures_by_root_cause: dict[str, int]
    avg_time_to_triage_hours: float | None
    avg_time_to_resolution_hours: float | None
    cases_added_per_dataset_version: dict[str, int]
    recurrence_rate: float
    reopen_rate: float
    regression_escape_rate: float | None
    fixed_case_confirmation_rate: float | None


def _avg_hours(deltas: list[float]) -> float | None:
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def compute_feedback_loop_metrics(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str | None = None,
) -> FeedbackLoopMetrics:
    statement = select(EvaluationCandidate).where(
        EvaluationCandidate.organisation_id == organisation_id,
        EvaluationCandidate.workspace_id == workspace_id,
    )
    if widget_id is not None:
        statement = statement.where(EvaluationCandidate.widget_id == widget_id)
    candidates = list(db.execute(statement).scalars().all())

    candidates_by_status = Counter(c.triage_status for c in candidates)
    candidates_by_signal_type = Counter(c.signal_type for c in candidates)
    candidates_by_severity = Counter(c.severity for c in candidates)
    failures_by_root_cause = Counter(c.root_cause_category for c in candidates if c.root_cause_category)

    triage_deltas = [
        (c.first_triaged_at - c.created_at).total_seconds() / 3600 for c in candidates if c.first_triaged_at is not None
    ]
    resolution_deltas = [
        (c.resolved_at - c.created_at).total_seconds() / 3600 for c in candidates if c.resolved_at is not None
    ]

    total = len(candidates)
    recurrence_rate = (sum(1 for c in candidates if c.occurrence_count > 1) / total) if total else 0.0
    reopen_rate = (sum(1 for c in candidates if c.is_reopen) / total) if total else 0.0

    version_events_statement = select(EvaluationDatasetVersionEvent).where(
        EvaluationDatasetVersionEvent.organisation_id == organisation_id,
        EvaluationDatasetVersionEvent.workspace_id == workspace_id,
    )
    version_events = list(db.execute(version_events_statement).scalars().all())
    cases_added_per_dataset_version = Counter(f"{event.dataset_id}:{event.to_version}" for event in version_events)

    promoted_case_ids = [c.promoted_case_id for c in candidates if c.promoted_case_id]
    fixed_count = escaped_count = 0
    confirmed_total = 0
    for case_id in promoted_case_ids:
        earliest_result = db.execute(
            select(EvaluationResult).where(EvaluationResult.case_id == case_id).order_by(EvaluationResult.created_at.asc()).limit(1)
        ).scalar_one_or_none()
        if earliest_result is None:
            continue
        confirmed_total += 1
        if earliest_result.passed:
            fixed_count += 1
        else:
            escaped_count += 1

    regression_escape_rate = (escaped_count / confirmed_total) if confirmed_total else None
    fixed_case_confirmation_rate = (fixed_count / confirmed_total) if confirmed_total else None

    return FeedbackLoopMetrics(
        candidates_by_status=dict(candidates_by_status),
        candidates_by_signal_type=dict(candidates_by_signal_type),
        candidates_by_severity=dict(candidates_by_severity),
        failures_by_root_cause=dict(failures_by_root_cause),
        avg_time_to_triage_hours=_avg_hours(triage_deltas),
        avg_time_to_resolution_hours=_avg_hours(resolution_deltas),
        cases_added_per_dataset_version=dict(cases_added_per_dataset_version),
        recurrence_rate=recurrence_rate,
        reopen_rate=reopen_rate,
        regression_escape_rate=regression_escape_rate,
        fixed_case_confirmation_rate=fixed_case_confirmation_rate,
    )
