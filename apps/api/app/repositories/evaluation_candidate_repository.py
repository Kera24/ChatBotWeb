from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import EvaluationCandidate, EvaluationCase, EvaluationDataset, EvaluationDatasetVersionEvent, EvaluationRegressionReport
from app.evaluation.feedback.dedup import compute_dedup_hash
from app.evaluation.feedback.signals import SEVERE_ON_FIRST_OCCURRENCE, SEVERITY_LEVELS, TERMINAL_TRIAGE_STATUSES, TRIAGE_STATUSES
from app.observability.redaction import REDACTION_RULESET_VERSION, redact_free_text
from app.repositories.audit_repository import add_audit_event

_SEVERITY_ORDER = ("low", "medium", "high", "critical")
_RECURRENCE_ESCALATION_THRESHOLD = 3


class CandidateNotFound(LookupError):
    pass


class InvalidTriageStatus(ValueError):
    pass


class InvalidTriageTransition(ValueError):
    pass


class CandidateNotAccepted(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _escalate_severity(severity: str) -> str:
    try:
        index = _SEVERITY_ORDER.index(severity)
    except ValueError:
        return severity
    return _SEVERITY_ORDER[min(index + 1, len(_SEVERITY_ORDER) - 1)]


# --- candidates ---------------------------------------------------------------


def create_candidate(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    signal_type: str,
    severity: str,
    question: str,
    response: str | None,
    reason_code: str,
    source_trace_id: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    evidence_refs: list[dict] | None = None,
    metadata: dict | None = None,
    is_reopen: bool = False,
    occurrence_count: int = 1,
) -> EvaluationCandidate:
    redacted_question = redact_free_text(question).text if question else question
    redacted_response = redact_free_text(response).text if response else response
    dedup_hash = compute_dedup_hash(question, widget_id=widget_id, reason_code=reason_code)

    candidate = EvaluationCandidate(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        source_trace_id=source_trace_id,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        signal_type=signal_type,
        severity=severity,
        redacted_question=redacted_question,
        redacted_response=redacted_response,
        redaction_version=REDACTION_RULESET_VERSION,
        evidence_refs_json=evidence_refs or None,
        triage_status="new",
        dedup_hash=dedup_hash,
        occurrence_count=occurrence_count,
        is_reopen=is_reopen,
        metadata_json=metadata or None,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@dataclass(frozen=True)
class CreateOrBumpOutcome:
    candidate: EvaluationCandidate
    created: bool
    bumped: bool


def create_or_bump_candidate(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    signal_type: str,
    severity: str,
    question: str,
    response: str | None,
    reason_code: str,
    source_trace_id: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    evidence_refs: list[dict] | None = None,
    metadata: dict | None = None,
) -> CreateOrBumpOutcome:
    """Used by the automatic signal scanner (app.evaluation.feedback.detector).

    "Do not treat every fallback as a defect" is implemented as: a signal type
    outside SEVERE_ON_FIRST_OCCURRENCE starts at severity "low" on its first
    sighting and only escalates to the caller-supplied severity once it has
    recurred _RECURRENCE_ESCALATION_THRESHOLD times - a reviewer's default
    queue view can filter out low-severity singletons without the scanner
    silently dropping the signal (it is always recorded, just not loud)."""
    dedup_hash = compute_dedup_hash(question, widget_id=widget_id, reason_code=reason_code)

    unresolved = db.execute(
        select(EvaluationCandidate).where(
            EvaluationCandidate.organisation_id == organisation_id,
            EvaluationCandidate.workspace_id == workspace_id,
            EvaluationCandidate.dedup_hash == dedup_hash,
            EvaluationCandidate.triage_status.notin_(tuple(TERMINAL_TRIAGE_STATUSES)),
        )
    ).scalar_one_or_none()
    if unresolved is not None:
        unresolved.occurrence_count += 1
        if unresolved.occurrence_count >= _RECURRENCE_ESCALATION_THRESHOLD and unresolved.severity == "low":
            unresolved.severity = severity if severity != "low" else "medium"
        db.commit()
        db.refresh(unresolved)
        return CreateOrBumpOutcome(candidate=unresolved, created=False, bumped=True)

    resolved_match = db.execute(
        select(EvaluationCandidate)
        .where(
            EvaluationCandidate.organisation_id == organisation_id,
            EvaluationCandidate.workspace_id == workspace_id,
            EvaluationCandidate.dedup_hash == dedup_hash,
            EvaluationCandidate.triage_status == "resolved",
        )
        .order_by(EvaluationCandidate.resolved_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    is_reopen = resolved_match is not None
    initial_severity = severity if signal_type in {member.value for member in SEVERE_ON_FIRST_OCCURRENCE} else "low"
    if is_reopen:
        initial_severity = _escalate_severity(initial_severity)

    candidate = create_candidate(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        signal_type=signal_type,
        severity=initial_severity,
        question=question,
        response=response,
        reason_code=reason_code,
        source_trace_id=source_trace_id,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        evidence_refs=evidence_refs,
        metadata=metadata,
        is_reopen=is_reopen,
    )
    return CreateOrBumpOutcome(candidate=candidate, created=True, bumped=False)


def preview_dedup_outcome(db: Session, *, organisation_id: str, workspace_id: str, dedup_hash: str) -> str:
    """Read-only counterpart to create_or_bump_candidate's matching logic, for
    --dry-run scan reporting (a real dry run must not rely on rolling back a
    session that repository writes already committed mid-loop - see
    app.operations.production_signal_scan). Returns "bump" or "create"."""
    unresolved = db.execute(
        select(EvaluationCandidate.id).where(
            EvaluationCandidate.organisation_id == organisation_id,
            EvaluationCandidate.workspace_id == workspace_id,
            EvaluationCandidate.dedup_hash == dedup_hash,
            EvaluationCandidate.triage_status.notin_(tuple(TERMINAL_TRIAGE_STATUSES)),
        )
    ).scalar_one_or_none()
    return "bump" if unresolved is not None else "create"


def get_candidate(db: Session, *, organisation_id: str, workspace_id: str, candidate_id: str) -> EvaluationCandidate | None:
    statement = select(EvaluationCandidate).where(
        EvaluationCandidate.id == candidate_id,
        EvaluationCandidate.organisation_id == organisation_id,
        EvaluationCandidate.workspace_id == workspace_id,
    )
    return db.execute(statement).scalar_one_or_none()


def list_candidates(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str | None = None,
    triage_status: str | None = None,
    signal_type: str | None = None,
    severity: str | None = None,
    root_cause_category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[EvaluationCandidate]:
    statement = _filtered_candidates(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        triage_status=triage_status,
        signal_type=signal_type,
        severity=severity,
        root_cause_category=root_cause_category,
    )
    statement = statement.order_by(EvaluationCandidate.created_at.desc()).offset(max(0, offset)).limit(max(1, min(limit, 100)))
    return list(db.execute(statement).scalars().all())


def count_candidates(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str | None = None,
    triage_status: str | None = None,
    signal_type: str | None = None,
    severity: str | None = None,
    root_cause_category: str | None = None,
) -> int:
    statement = _filtered_candidates(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        triage_status=triage_status,
        signal_type=signal_type,
        severity=severity,
        root_cause_category=root_cause_category,
    )
    return int(db.execute(select(func.count()).select_from(statement.subquery())).scalar_one() or 0)


def _filtered_candidates(
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str | None,
    triage_status: str | None,
    signal_type: str | None,
    severity: str | None,
    root_cause_category: str | None,
):
    statement = select(EvaluationCandidate).where(
        EvaluationCandidate.organisation_id == organisation_id,
        EvaluationCandidate.workspace_id == workspace_id,
    )
    if widget_id is not None:
        statement = statement.where(EvaluationCandidate.widget_id == widget_id)
    if triage_status is not None:
        statement = statement.where(EvaluationCandidate.triage_status == triage_status)
    if signal_type is not None:
        statement = statement.where(EvaluationCandidate.signal_type == signal_type)
    if severity is not None:
        statement = statement.where(EvaluationCandidate.severity == severity)
    if root_cause_category is not None:
        statement = statement.where(EvaluationCandidate.root_cause_category == root_cause_category)
    return statement


def update_triage(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    candidate_id: str,
    actor_user_id: str | None,
    triage_status: str | None = None,
    severity: str | None = None,
    root_cause_category: str | None = None,
    expected_document_ids: list[str] | None = None,
    expected_source_labels: list[str] | None = None,
    expected_answerability: str | None = None,
    triage_details: dict | None = None,
    expected_behaviour_note: str | None = None,
    reviewer_id: str | None = None,
    notes: str | None = None,
) -> EvaluationCandidate:
    candidate = get_candidate(db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate_id)
    if candidate is None:
        raise CandidateNotFound("Evaluation candidate not found for tenant workspace.")

    previous_status = candidate.triage_status
    if triage_status is not None:
        if triage_status not in TRIAGE_STATUSES:
            raise InvalidTriageStatus(f"Unsupported triage status {triage_status!r}.")
        if previous_status in TERMINAL_TRIAGE_STATUSES and triage_status != previous_status:
            raise InvalidTriageTransition(f"Cannot move a {previous_status!r} candidate to {triage_status!r}; it is already resolved.")
        candidate.triage_status = triage_status
        if previous_status == "new" and triage_status != "new" and candidate.first_triaged_at is None:
            candidate.first_triaged_at = _now()
        if triage_status in TERMINAL_TRIAGE_STATUSES:
            candidate.resolved_at = _now()

    if severity is not None:
        if severity not in SEVERITY_LEVELS:
            raise InvalidTriageStatus(f"Unsupported severity {severity!r}.")
        candidate.severity = severity
    if root_cause_category is not None:
        candidate.root_cause_category = root_cause_category
    if expected_document_ids is not None:
        candidate.expected_document_ids_json = expected_document_ids
    if expected_source_labels is not None:
        candidate.expected_source_labels_json = expected_source_labels
    if expected_answerability is not None:
        candidate.expected_answerability = expected_answerability
    if triage_details is not None:
        candidate.triage_details_json = triage_details
    if expected_behaviour_note is not None:
        candidate.expected_behaviour_note = expected_behaviour_note
    if reviewer_id is not None:
        candidate.reviewer_id = reviewer_id
    if notes is not None:
        candidate.notes = notes

    db.add(candidate)
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        action="evaluation_candidate.triaged",
        entity_type="evaluation_candidate",
        entity_id=candidate_id,
        actor_user_id=actor_user_id,
        previous_status=previous_status,
        new_status=candidate.triage_status,
        metadata_json={"signal_type": candidate.signal_type, "severity": candidate.severity},
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def mark_duplicate(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    candidate_id: str,
    duplicate_of_id: str,
    actor_user_id: str | None,
) -> EvaluationCandidate:
    candidate = update_triage(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        candidate_id=candidate_id,
        actor_user_id=actor_user_id,
        triage_status="duplicate",
    )
    candidate.duplicate_of_id = duplicate_of_id
    db.commit()
    db.refresh(candidate)
    return candidate


def _increment_dataset_version(current_version: str) -> str:
    try:
        return str(int(current_version) + 1)
    except ValueError:
        return f"{current_version}.{int(time.time())}"


def promote_candidate(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    candidate_id: str,
    dataset_id: str,
    reviewer_id: str | None,
    changelog_note: str | None,
) -> tuple[EvaluationCandidate, EvaluationCase, EvaluationDatasetVersionEvent]:
    candidate = get_candidate(db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate_id)
    if candidate is None:
        raise CandidateNotFound("Evaluation candidate not found for tenant workspace.")
    if candidate.triage_status != "accepted":
        raise CandidateNotAccepted("Only candidates with triage_status='accepted' can be promoted to a golden case.")

    dataset = db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.organisation_id == organisation_id,
            EvaluationDataset.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if dataset is None:
        raise CandidateNotFound("Evaluation dataset not found for tenant workspace.")

    case_metadata = dict(candidate.triage_details_json or {})
    case_metadata["source_signal_type"] = candidate.signal_type
    case_metadata["source_candidate_id"] = candidate.id

    case = EvaluationCase(
        dataset_id=dataset.id,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        question=candidate.redacted_question or "",
        reference_answer=candidate.redacted_response,
        expected_document_ids=candidate.expected_document_ids_json,
        expected_source_labels=candidate.expected_source_labels_json,
        expected_answerability=candidate.expected_answerability or "answerable",
        category=candidate.root_cause_category or "answerable_factual",
        tags=["production-feedback"],
        metadata_json=case_metadata,
        source_candidate_id=candidate.id,
    )
    db.add(case)
    db.flush()

    from_version = dataset.version
    to_version = _increment_dataset_version(from_version)
    dataset.version = to_version
    db.add(dataset)

    version_event = EvaluationDatasetVersionEvent(
        dataset_id=dataset.id,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        from_version=from_version,
        to_version=to_version,
        case_id=case.id,
        candidate_id=candidate.id,
        created_by=reviewer_id,
        changelog_note=changelog_note,
    )
    db.add(version_event)

    candidate.promoted_case_id = case.id
    candidate.dataset_destination_id = dataset.id
    db.add(candidate)

    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        action="evaluation_candidate.promoted",
        entity_type="evaluation_candidate",
        entity_id=candidate.id,
        actor_user_id=reviewer_id,
        previous_status="accepted",
        new_status="accepted",
        metadata_json={"case_id": case.id, "dataset_id": dataset.id, "from_version": from_version, "to_version": to_version},
    )

    db.commit()
    db.refresh(candidate)
    db.refresh(case)
    db.refresh(version_event)
    return candidate, case, version_event


# --- dataset version events ----------------------------------------------------


def list_dataset_version_events(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    dataset_id: str | None = None,
    limit: int = 100,
) -> list[EvaluationDatasetVersionEvent]:
    statement = select(EvaluationDatasetVersionEvent).where(
        EvaluationDatasetVersionEvent.organisation_id == organisation_id,
        EvaluationDatasetVersionEvent.workspace_id == workspace_id,
    )
    if dataset_id is not None:
        statement = statement.where(EvaluationDatasetVersionEvent.dataset_id == dataset_id)
    statement = statement.order_by(EvaluationDatasetVersionEvent.created_at.desc()).limit(limit)
    return list(db.execute(statement).scalars().all())


# --- regression reports ---------------------------------------------------------


def create_regression_report(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    dataset_id: str,
    run_id: str,
    baseline_run_id: str | None,
    report: dict,
    verdict_passed: bool,
    verdict_reasons: list[str] | None,
    created_by: str | None,
) -> EvaluationRegressionReport:
    regression_report = EvaluationRegressionReport(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        dataset_id=dataset_id,
        run_id=run_id,
        baseline_run_id=baseline_run_id,
        report_json=report,
        verdict_passed=verdict_passed,
        verdict_reasons_json=verdict_reasons,
        created_by=created_by,
    )
    db.add(regression_report)
    db.commit()
    db.refresh(regression_report)
    return regression_report


def list_regression_reports(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    dataset_id: str | None = None,
    limit: int = 50,
) -> list[EvaluationRegressionReport]:
    statement = select(EvaluationRegressionReport).where(
        EvaluationRegressionReport.organisation_id == organisation_id,
        EvaluationRegressionReport.workspace_id == workspace_id,
    )
    if dataset_id is not None:
        statement = statement.where(EvaluationRegressionReport.dataset_id == dataset_id)
    statement = statement.order_by(EvaluationRegressionReport.created_at.desc()).limit(limit)
    return list(db.execute(statement).scalars().all())


def get_regression_report(db: Session, *, organisation_id: str, workspace_id: str, report_id: str) -> EvaluationRegressionReport | None:
    statement = select(EvaluationRegressionReport).where(
        EvaluationRegressionReport.id == report_id,
        EvaluationRegressionReport.organisation_id == organisation_id,
        EvaluationRegressionReport.workspace_id == workspace_id,
    )
    return db.execute(statement).scalar_one_or_none()
