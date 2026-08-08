from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.db.models import AITrace
from app.evaluation.feedback.dedup import find_potential_duplicates
from app.evaluation.feedback_metrics import compute_feedback_loop_metrics
from app.repositories import evaluation_candidate_repository
from app.repositories.observability_repository import get_trace_detail
from app.repositories.evaluation_candidate_repository import (
    CandidateNotAccepted,
    CandidateNotFound,
    InvalidTriageStatus,
    InvalidTriageTransition,
)
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.evaluation_candidate import (
    DuplicateSuggestionRead,
    EvaluationCandidateCreate,
    EvaluationCandidateDetailRead,
    EvaluationCandidateMarkDuplicate,
    EvaluationCandidatePromote,
    EvaluationCandidateRead,
    EvaluationCandidateTriageUpdate,
    EvaluationDatasetVersionEventRead,
    EvaluationRegressionReportRead,
    FeedbackLoopMetricsRead,
)

router = APIRouter()

# Mirrors app.api.v1.review's ReviewReaderDependency/ReviewUpdaterDependency
# shape - reads open to viewer, triage/promote actions restricted to
# org_owner/client_admin.
FeedbackLoopReaderDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]
FeedbackLoopTriagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]

MAX_LIST_LIMIT = 100


def _ensure_workspace(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


def _duplicate_suggestions_for(db: DbSession, *, organisation_id: str, workspace_id: str, candidate) -> list[DuplicateSuggestionRead]:
    if not candidate.redacted_question:
        return []
    suggestions = find_potential_duplicates(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=candidate.widget_id,
        question=candidate.redacted_question,
        dedup_hash=candidate.dedup_hash,
        exclude_candidate_id=candidate.id,
    )
    return [
        DuplicateSuggestionRead(
            candidate_id=suggestion.candidate.id,
            match_reason=suggestion.match_reason,
            similarity=suggestion.similarity,
            redacted_question=suggestion.candidate.redacted_question,
            triage_status=suggestion.candidate.triage_status,
        )
        for suggestion in suggestions
    ]


@router.get("/{workspace_id}/evaluation-candidates")
def list_candidates(
    workspace_id: str,
    db: DbSession,
    _current_user: FeedbackLoopReaderDependency,
    organisation_id: str = Query(...),
    widget_id: str | None = Query(default=None),
    triage_status: str | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    root_cause_category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    candidates = evaluation_candidate_repository.list_candidates(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        triage_status=triage_status,
        signal_type=signal_type,
        severity=severity,
        root_cause_category=root_cause_category,
        limit=limit,
        offset=offset,
    )
    total = evaluation_candidate_repository.count_candidates(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        triage_status=triage_status,
        signal_type=signal_type,
        severity=severity,
        root_cause_category=root_cause_category,
    )
    data = [EvaluationCandidateRead.model_validate(candidate).model_dump(mode="json") for candidate in candidates]
    return success_response(data, meta={"limit": limit, "offset": offset, "count": len(data), "total": total})


@router.get("/{workspace_id}/evaluation-candidates/metrics")
def get_metrics(
    workspace_id: str,
    db: DbSession,
    _current_user: FeedbackLoopReaderDependency,
    organisation_id: str = Query(...),
    widget_id: str | None = Query(default=None),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    metrics = compute_feedback_loop_metrics(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    return success_response(FeedbackLoopMetricsRead(**metrics.__dict__).model_dump(mode="json"))


@router.post("/{workspace_id}/evaluation-candidates", status_code=status.HTTP_201_CREATED)
def create_candidate(
    workspace_id: str,
    payload: EvaluationCandidateCreate,
    db: DbSession,
    current_user: FeedbackLoopTriagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        payload.validate_vocabulary()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # payload.source_trace_id is the public, URL-facing `AITrace.trace_id`
    # correlation string (what observability pages link with) - the FK column
    # on EvaluationCandidate targets the internal AITrace.id primary key, so
    # it must be resolved here rather than stored as-is.
    resolved_trace_id: str | None = None
    if payload.source_trace_id:
        trace_detail = get_trace_detail(db, organisation_id=organisation_id, workspace_id=workspace_id, trace_id=payload.source_trace_id)
        if trace_detail is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="source_trace_id does not reference an existing trace.")
        resolved_trace_id = trace_detail.trace.id

    candidate = evaluation_candidate_repository.create_candidate(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=payload.widget_id,
        signal_type=payload.signal_type,
        severity=payload.severity,
        question=payload.question,
        response=payload.response,
        reason_code=payload.reason_code,
        source_trace_id=resolved_trace_id,
        source_conversation_id=payload.source_conversation_id,
        source_message_id=payload.source_message_id,
        evidence_refs=payload.evidence_refs,
        metadata={"created_by": current_user.user_id, "notes_at_creation": payload.notes} if payload.notes else None,
    )
    return success_response(EvaluationCandidateRead.model_validate(candidate).model_dump(mode="json"))


@router.get("/{workspace_id}/evaluation-candidates/{candidate_id}")
def get_candidate_detail(
    workspace_id: str,
    candidate_id: str,
    db: DbSession,
    _current_user: FeedbackLoopReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    candidate = evaluation_candidate_repository.get_candidate(db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation candidate not found.")
    source_trace_public_id = None
    if candidate.source_trace_id:
        trace_row = db.get(AITrace, candidate.source_trace_id)
        source_trace_public_id = trace_row.trace_id if trace_row is not None else None
    detail = EvaluationCandidateDetailRead(
        candidate=EvaluationCandidateRead.model_validate(candidate),
        potential_duplicates=_duplicate_suggestions_for(db, organisation_id=organisation_id, workspace_id=workspace_id, candidate=candidate),
        source_trace_public_id=source_trace_public_id,
    )
    return success_response(detail.model_dump(mode="json"))


@router.patch("/{workspace_id}/evaluation-candidates/{candidate_id}")
def update_candidate_triage(
    workspace_id: str,
    candidate_id: str,
    payload: EvaluationCandidateTriageUpdate,
    db: DbSession,
    current_user: FeedbackLoopTriagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    try:
        payload.validate_vocabulary()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        candidate = evaluation_candidate_repository.update_triage(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            actor_user_id=current_user.user_id,
            triage_status=payload.triage_status,
            severity=payload.severity,
            root_cause_category=payload.root_cause_category,
            expected_document_ids=payload.expected_document_ids,
            expected_source_labels=payload.expected_source_labels,
            expected_answerability=payload.expected_answerability,
            triage_details=payload.triage_details,
            expected_behaviour_note=payload.expected_behaviour_note,
            reviewer_id=current_user.user_id,
            notes=payload.notes,
        )
    except CandidateNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation candidate not found.") from exc
    except (InvalidTriageStatus, InvalidTriageTransition) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return success_response(EvaluationCandidateRead.model_validate(candidate).model_dump(mode="json"))


@router.post("/{workspace_id}/evaluation-candidates/{candidate_id}/mark-duplicate")
def mark_candidate_duplicate(
    workspace_id: str,
    candidate_id: str,
    payload: EvaluationCandidateMarkDuplicate,
    db: DbSession,
    current_user: FeedbackLoopTriagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    duplicate_target = evaluation_candidate_repository.get_candidate(
        db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=payload.duplicate_of_id
    )
    if duplicate_target is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="duplicate_of_id does not reference an existing candidate.")
    try:
        candidate = evaluation_candidate_repository.mark_duplicate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            duplicate_of_id=payload.duplicate_of_id,
            actor_user_id=current_user.user_id,
        )
    except CandidateNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation candidate not found.") from exc
    except InvalidTriageTransition as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response(EvaluationCandidateRead.model_validate(candidate).model_dump(mode="json"))


@router.post("/{workspace_id}/evaluation-candidates/{candidate_id}/promote", status_code=status.HTTP_201_CREATED)
def promote_candidate(
    workspace_id: str,
    candidate_id: str,
    payload: EvaluationCandidatePromote,
    db: DbSession,
    current_user: FeedbackLoopTriagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    try:
        candidate, case, version_event = evaluation_candidate_repository.promote_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            dataset_id=payload.dataset_id,
            reviewer_id=current_user.user_id,
            changelog_note=payload.changelog_note,
        )
    except CandidateNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CandidateNotAccepted as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return success_response(
        {
            "candidate": EvaluationCandidateRead.model_validate(candidate).model_dump(mode="json"),
            "case_id": case.id,
            "dataset_version_event": EvaluationDatasetVersionEventRead.model_validate(version_event).model_dump(mode="json"),
        }
    )


@router.get("/{workspace_id}/evaluation-dataset-versions")
def list_dataset_version_events(
    workspace_id: str,
    db: DbSession,
    _current_user: FeedbackLoopReaderDependency,
    organisation_id: str = Query(...),
    dataset_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    events = evaluation_candidate_repository.list_dataset_version_events(
        db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id, limit=limit
    )
    return success_response([EvaluationDatasetVersionEventRead.model_validate(event).model_dump(mode="json") for event in events])


@router.get("/{workspace_id}/evaluation-regression-reports")
def list_regression_reports(
    workspace_id: str,
    db: DbSession,
    _current_user: FeedbackLoopReaderDependency,
    organisation_id: str = Query(...),
    dataset_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    reports = evaluation_candidate_repository.list_regression_reports(
        db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id, limit=limit
    )
    return success_response([EvaluationRegressionReportRead.model_validate(report).model_dump(mode="json") for report in reports])


@router.get("/{workspace_id}/evaluation-regression-reports/{report_id}")
def get_regression_report_detail(
    workspace_id: str,
    report_id: str,
    db: DbSession,
    _current_user: FeedbackLoopReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    report = evaluation_candidate_repository.get_regression_report(db, organisation_id=organisation_id, workspace_id=workspace_id, report_id=report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regression report not found.")
    return success_response(EvaluationRegressionReportRead.model_validate(report).model_dump(mode="json"))
