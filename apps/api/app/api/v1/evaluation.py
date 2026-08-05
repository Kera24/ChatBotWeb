from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.evaluation.engine import EmptyDatasetError, EvaluationRunOptions, run_evaluation
from app.evaluation.gate import evaluate_gate
from app.evaluation.metrics.aggregate import compare_to_baseline
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.evaluation import (
    EvaluationCaseCreate,
    EvaluationCaseRead,
    EvaluationCaseUpdate,
    EvaluationDatasetCreate,
    EvaluationDatasetDetail,
    EvaluationDatasetRead,
    EvaluationRunCreate,
    EvaluationRunRead,
    EvaluationResultRead,
)

router = APIRouter()

# "reviewer" has no dedicated role in this codebase; read access on evaluation
# runs/results follows the existing review-queue convention of allowing the
# same roles that can already read conversations/review items (viewer included).
EvaluationReaderDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]
EvaluationManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


def _ensure_workspace(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


@router.get("/{workspace_id}/evaluation/datasets")
def list_datasets(
    workspace_id: str,
    db: DbSession,
    _current_user: EvaluationReaderDependency,
    organisation_id: str = Query(...),
    widget_id: str | None = Query(default=None),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    datasets = evaluation_repository.list_datasets(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    return success_response([EvaluationDatasetRead.model_validate(dataset).model_dump(mode="json") for dataset in datasets])


@router.post("/{workspace_id}/evaluation/datasets", status_code=status.HTTP_201_CREATED)
def create_dataset(
    workspace_id: str,
    payload: EvaluationDatasetCreate,
    db: DbSession,
    current_user: EvaluationManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    dataset = evaluation_repository.create_dataset(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=payload.widget_id,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        created_by=current_user.user_id,
    )
    return success_response(EvaluationDatasetRead.model_validate(dataset).model_dump(mode="json"))


@router.get("/{workspace_id}/evaluation/datasets/{dataset_id}")
def get_dataset_detail(
    workspace_id: str,
    dataset_id: str,
    db: DbSession,
    _current_user: EvaluationReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    dataset = evaluation_repository.get_dataset(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation dataset not found.")
    cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=dataset.id)
    detail = EvaluationDatasetDetail(
        **EvaluationDatasetRead.model_validate(dataset).model_dump(),
        cases=[EvaluationCaseRead.model_validate(case) for case in cases],
    )
    return success_response(detail.model_dump(mode="json"))


@router.post("/{workspace_id}/evaluation/datasets/{dataset_id}/cases", status_code=status.HTTP_201_CREATED)
def create_case(
    workspace_id: str,
    dataset_id: str,
    payload: EvaluationCaseCreate,
    db: DbSession,
    _current_user: EvaluationManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    dataset = evaluation_repository.get_dataset(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation dataset not found.")
    try:
        payload.validate_vocabulary()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    case = evaluation_repository.create_case(
        db,
        dataset=dataset,
        question=payload.question,
        reference_answer=payload.reference_answer,
        expected_document_ids=payload.expected_document_ids,
        expected_source_labels=payload.expected_source_labels,
        expected_answerability=payload.expected_answerability,
        category=payload.category,
        tags=payload.tags,
        metadata_json=payload.metadata_json,
    )
    return success_response(EvaluationCaseRead.model_validate(case).model_dump(mode="json"))


@router.patch("/{workspace_id}/evaluation/datasets/{dataset_id}/cases/{case_id}")
def update_case(
    workspace_id: str,
    dataset_id: str,
    case_id: str,
    payload: EvaluationCaseUpdate,
    db: DbSession,
    _current_user: EvaluationManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    case = evaluation_repository.get_case(db, organisation_id=organisation_id, workspace_id=workspace_id, case_id=case_id)
    if case is None or case.dataset_id != dataset_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation case not found.")
    updates = payload.model_dump(exclude_unset=True)
    case = evaluation_repository.update_case(db, case=case, updates=updates)
    return success_response(EvaluationCaseRead.model_validate(case).model_dump(mode="json"))


@router.post("/{workspace_id}/evaluation/runs", status_code=status.HTTP_201_CREATED)
def start_run(
    workspace_id: str,
    payload: EvaluationRunCreate,
    db: DbSession,
    current_user: EvaluationManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    dataset = evaluation_repository.get_dataset(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation dataset not found.")
    if payload.mode not in {"mock", "live"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be 'mock' or 'live'.")

    try:
        run = run_evaluation(
            db,
            dataset=dataset,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=payload.widget_id,
            options=EvaluationRunOptions(mode=payload.mode, policy=load_policy_from_env(), created_by=current_user.user_id),
        )
    except EmptyDatasetError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_response(EvaluationRunRead.model_validate(run).model_dump(mode="json"))


@router.get("/{workspace_id}/evaluation/runs")
def list_runs(
    workspace_id: str,
    db: DbSession,
    _current_user: EvaluationReaderDependency,
    organisation_id: str = Query(...),
    dataset_id: str | None = Query(default=None),
    limit: int = 50,
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    bounded_limit = min(max(limit, 1), 200)
    runs = evaluation_repository.list_runs(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id, limit=bounded_limit)
    return success_response([EvaluationRunRead.model_validate(run).model_dump(mode="json") for run in runs], meta={"limit": bounded_limit})


@router.get("/{workspace_id}/evaluation/runs/compare")
def compare_runs(
    workspace_id: str,
    db: DbSession,
    _current_user: EvaluationReaderDependency,
    organisation_id: str = Query(...),
    baseline_run_id: str = Query(...),
    candidate_run_id: str = Query(...),
) -> dict[str, object]:
    baseline_run = _get_run_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=baseline_run_id)
    candidate_run = _get_run_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=candidate_run_id)
    baseline_summary = build_run_summary(db, run_id=baseline_run.id)
    candidate_summary = build_run_summary(db, run_id=candidate_run.id)

    return success_response({
        "baseline": {"run": EvaluationRunRead.model_validate(baseline_run).model_dump(mode="json"), "summary": baseline_summary.as_dict()},
        "candidate": {"run": EvaluationRunRead.model_validate(candidate_run).model_dump(mode="json"), "summary": candidate_summary.as_dict()},
        "comparison": compare_to_baseline(candidate_summary, baseline_summary),
    })


@router.get("/{workspace_id}/evaluation/runs/{run_id}")
def get_run(
    workspace_id: str,
    run_id: str,
    db: DbSession,
    _current_user: EvaluationReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    run = _get_run_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=run_id)
    summary = build_run_summary(db, run_id=run.id)
    gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)
    return success_response({
        "run": EvaluationRunRead.model_validate(run).model_dump(mode="json"),
        "summary": summary.as_dict(),
        "gate": gate.as_dict(),
    })


@router.get("/{workspace_id}/evaluation/runs/{run_id}/results")
def list_run_results(
    workspace_id: str,
    run_id: str,
    db: DbSession,
    _current_user: EvaluationReaderDependency,
    organisation_id: str = Query(...),
    only_failed: bool = Query(default=False),
) -> dict[str, object]:
    _get_run_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=run_id)
    results = evaluation_repository.list_results_for_run(db, run_id=run_id, only_failed=only_failed)
    return success_response([EvaluationResultRead.model_validate(result).model_dump(mode="json") for result in results])


@router.get("/{workspace_id}/evaluation/runs/{run_id}/results/{case_id}")
def get_run_result_detail(
    workspace_id: str,
    run_id: str,
    case_id: str,
    db: DbSession,
    _current_user: EvaluationReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _get_run_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=run_id)
    result = evaluation_repository.get_result_for_case(db, run_id=run_id, case_id=case_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation result not found.")
    case = evaluation_repository.get_case(db, organisation_id=organisation_id, workspace_id=workspace_id, case_id=case_id)
    return success_response({
        "result": EvaluationResultRead.model_validate(result).model_dump(mode="json"),
        "case": EvaluationCaseRead.model_validate(case).model_dump(mode="json") if case is not None else None,
    })


def _get_run_or_404(db: DbSession, *, organisation_id: str, workspace_id: str, run_id: str):
    run = evaluation_repository.get_run(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found.")
    return run
