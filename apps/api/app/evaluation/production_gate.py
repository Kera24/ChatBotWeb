"""Release gate for the production feedback loop (spec section 9) - decides
whether it is safe to deploy given the current state of triaged production
failures, the latest evaluation run, and the dataset version history.

Deployment-agnostic like app.evaluation.gate: returns a plain GateVerdict: the
caller (app.operations.eval_release_gate_check, then
scripts/release-gate.mjs) turns that into a process exit code.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationCandidate, EvaluationDataset, EvaluationDatasetVersionEvent, EvaluationRegressionReport, EvaluationRun
from app.evaluation.categories import ISOLATION_CATEGORIES
from app.evaluation.gate import GateVerdict
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository

DEFAULT_MAX_BASELINE_AGE_DAYS = 7


def _as_aware_utc(value: datetime) -> datetime:
    # SQLite round-trips DateTime columns as naive even when an aware value
    # was written (unlike Postgres); every completed_at in this codebase is
    # written via datetime.now(timezone.utc), so a naive value read back is
    # always UTC in practice.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _latest_completed_run(db: Session, *, organisation_id: str, workspace_id: str, dataset_id: str) -> EvaluationRun | None:
    statement = (
        select(EvaluationRun)
        .where(
            EvaluationRun.organisation_id == organisation_id,
            EvaluationRun.workspace_id == workspace_id,
            EvaluationRun.dataset_id == dataset_id,
            EvaluationRun.status == "completed",
        )
        .order_by(EvaluationRun.completed_at.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def _previous_completed_run(db: Session, *, organisation_id: str, workspace_id: str, dataset_id: str, before_run_id: str) -> EvaluationRun | None:
    latest = evaluation_repository.get_run(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=before_run_id)
    if latest is None or latest.completed_at is None:
        return None
    statement = (
        select(EvaluationRun)
        .where(
            EvaluationRun.organisation_id == organisation_id,
            EvaluationRun.workspace_id == workspace_id,
            EvaluationRun.dataset_id == dataset_id,
            EvaluationRun.status == "completed",
            EvaluationRun.id != before_run_id,
            EvaluationRun.completed_at < latest.completed_at,
        )
        .order_by(EvaluationRun.completed_at.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def evaluate_production_readiness(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    dataset_id: str,
    max_baseline_age_days: int = DEFAULT_MAX_BASELINE_AGE_DAYS,
) -> GateVerdict:
    reasons: list[str] = []

    dataset = db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id, EvaluationDataset.organisation_id == organisation_id, EvaluationDataset.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if dataset is None:
        return GateVerdict(passed=False, reasons=[f"dataset {dataset_id} not found for tenant workspace"])

    latest_run = _latest_completed_run(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id)
    if latest_run is None:
        return GateVerdict(passed=False, reasons=["no completed evaluation run exists for this dataset"])

    # 1. Dataset version changed since the latest completed run.
    if dataset.version != latest_run.dataset_version:
        reasons.append(
            f"dataset version is {dataset.version!r} but the latest completed run ({latest_run.id}) ran against version "
            f"{latest_run.dataset_version!r} - no completed evaluation exists at the current version"
        )

    # 2. Stale baseline.
    if latest_run.completed_at is not None:
        age = datetime.now(timezone.utc) - _as_aware_utc(latest_run.completed_at)
        if age > timedelta(days=max_baseline_age_days):
            reasons.append(f"latest completed run ({latest_run.id}) is {age.days} day(s) old, exceeding the {max_baseline_age_days}-day baseline freshness limit")

    # 3. Hard deterministic failures in the latest run.
    if latest_run.hard_failure_cases > 0:
        reasons.append(f"latest completed run ({latest_run.id}) has {latest_run.hard_failure_cases} hard failure(s)")

    # 4. Isolation/citation regression vs. the previous baseline.
    previous_run = _previous_completed_run(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id, before_run_id=latest_run.id)
    if previous_run is not None:
        latest_summary = build_run_summary(db, run_id=latest_run.id)
        previous_summary = build_run_summary(db, run_id=previous_run.id)
        isolation_values = {member.value for member in ISOLATION_CATEGORIES}
        latest_isolation_hard_failures = sum(
            bucket.get("hard_failure", 0) for category, bucket in latest_summary.category_breakdown.items() if category in isolation_values
        )
        previous_isolation_hard_failures = sum(
            bucket.get("hard_failure", 0) for category, bucket in previous_summary.category_breakdown.items() if category in isolation_values
        )
        if latest_isolation_hard_failures > previous_isolation_hard_failures:
            reasons.append(
                f"isolation-category hard failures increased from {previous_isolation_hard_failures} to {latest_isolation_hard_failures} versus the previous baseline"
            )
        if latest_summary.citation_coverage < previous_summary.citation_coverage:
            reasons.append(
                f"citation coverage regressed from {previous_summary.citation_coverage:.2%} to {latest_summary.citation_coverage:.2%} versus the previous baseline"
            )

    # 5. Any accepted+promoted production failure case still failing (or never
    #    actually evaluated) in the latest completed run.
    accepted_promoted = db.execute(
        select(EvaluationCandidate).where(
            EvaluationCandidate.organisation_id == organisation_id,
            EvaluationCandidate.workspace_id == workspace_id,
            EvaluationCandidate.dataset_destination_id == dataset_id,
            EvaluationCandidate.triage_status == "accepted",
            EvaluationCandidate.promoted_case_id.isnot(None),
        )
    ).scalars().all()
    for candidate in accepted_promoted:
        result = evaluation_repository.get_result_for_case(db, run_id=latest_run.id, case_id=candidate.promoted_case_id)
        if result is None:
            reasons.append(f"approved production case (candidate {candidate.id}) was not evaluated in the latest completed run - evidence incomplete")
        elif not result.passed or result.hard_failure:
            reasons.append(f"approved production case (candidate {candidate.id}, case {candidate.promoted_case_id}) still fails in the latest completed run")

    # 6. Missing regression report evidence for the latest dataset version bump.
    latest_version_event = db.execute(
        select(EvaluationDatasetVersionEvent)
        .where(EvaluationDatasetVersionEvent.dataset_id == dataset_id, EvaluationDatasetVersionEvent.organisation_id == organisation_id)
        .order_by(EvaluationDatasetVersionEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_version_event is not None:
        has_report_since = db.execute(
            select(EvaluationRegressionReport.id)
            .where(
                EvaluationRegressionReport.dataset_id == dataset_id,
                EvaluationRegressionReport.organisation_id == organisation_id,
                EvaluationRegressionReport.created_at >= latest_version_event.created_at,
            )
            .limit(1)
        ).scalar_one_or_none()
        if has_report_since is None:
            reasons.append(
                f"dataset version was bumped to {latest_version_event.to_version!r} on {latest_version_event.created_at.isoformat()} "
                "but no regression report has been produced since - required evaluation evidence is incomplete"
            )

    return GateVerdict(passed=len(reasons) == 0, reasons=reasons)
