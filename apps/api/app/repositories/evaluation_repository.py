from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvaluationCase, EvaluationDataset, EvaluationResult, EvaluationRun


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- datasets -----------------------------------------------------------------


def create_dataset(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    name: str,
    description: str | None,
    version: str,
    created_by: str | None,
) -> EvaluationDataset:
    dataset = EvaluationDataset(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        name=name,
        description=description,
        version=version,
        status="draft",
        created_by=created_by,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def get_dataset(db: Session, *, organisation_id: str, workspace_id: str, dataset_id: str) -> EvaluationDataset | None:
    statement = select(EvaluationDataset).where(
        EvaluationDataset.id == dataset_id,
        EvaluationDataset.organisation_id == organisation_id,
        EvaluationDataset.workspace_id == workspace_id,
    )
    return db.execute(statement).scalar_one_or_none()


def list_datasets(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str | None = None) -> list[EvaluationDataset]:
    statement = select(EvaluationDataset).where(
        EvaluationDataset.organisation_id == organisation_id,
        EvaluationDataset.workspace_id == workspace_id,
    )
    if widget_id is not None:
        statement = statement.where(EvaluationDataset.widget_id == widget_id)
    statement = statement.order_by(EvaluationDataset.created_at.desc())
    return list(db.execute(statement).scalars().all())


# --- cases ----------------------------------------------------------------


def create_case(
    db: Session,
    *,
    dataset: EvaluationDataset,
    question: str,
    reference_answer: str | None,
    expected_document_ids: list[str] | None,
    expected_source_labels: list[str] | None,
    expected_answerability: str,
    category: str,
    tags: list[str] | None,
    metadata_json: dict | None,
) -> EvaluationCase:
    case = EvaluationCase(
        dataset_id=dataset.id,
        organisation_id=dataset.organisation_id,
        workspace_id=dataset.workspace_id,
        question=question,
        reference_answer=reference_answer,
        expected_document_ids=expected_document_ids,
        expected_source_labels=expected_source_labels,
        expected_answerability=expected_answerability,
        category=category,
        tags=tags,
        metadata_json=metadata_json,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def update_case(db: Session, *, case: EvaluationCase, updates: dict) -> EvaluationCase:
    for field, value in updates.items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    return case


def get_case(db: Session, *, organisation_id: str, workspace_id: str, case_id: str) -> EvaluationCase | None:
    statement = select(EvaluationCase).where(
        EvaluationCase.id == case_id,
        EvaluationCase.organisation_id == organisation_id,
        EvaluationCase.workspace_id == workspace_id,
    )
    return db.execute(statement).scalar_one_or_none()


def list_cases_for_dataset(db: Session, *, dataset_id: str) -> list[EvaluationCase]:
    statement = select(EvaluationCase).where(EvaluationCase.dataset_id == dataset_id).order_by(EvaluationCase.created_at.asc())
    return list(db.execute(statement).scalars().all())


# --- runs -------------------------------------------------------------------


def create_run(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    dataset: EvaluationDataset,
    mode: str,
    policy_snapshot: dict,
    retrieval_settings: dict | None,
    created_by: str | None,
) -> EvaluationRun:
    run = EvaluationRun(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        mode=mode,
        status="pending",
        policy_snapshot_json=policy_snapshot,
        retrieval_settings_json=retrieval_settings,
        created_by=created_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def mark_run_started(db: Session, *, run: EvaluationRun) -> EvaluationRun:
    run.status = "running"
    run.started_at = _now()
    db.commit()
    db.refresh(run)
    return run


def mark_run_completed(
    db: Session,
    *,
    run: EvaluationRun,
    status: str,
    total_cases: int,
    passed_cases: int,
    failed_cases: int,
    hard_failure_cases: int,
    provider_key: str | None,
    model_key: str | None,
    provider_model_name: str | None,
    prompt_key: str | None,
    prompt_version: str | None,
    prompt_hash: str | None,
) -> EvaluationRun:
    run.status = status
    run.total_cases = total_cases
    run.passed_cases = passed_cases
    run.failed_cases = failed_cases
    run.hard_failure_cases = hard_failure_cases
    run.provider_key = provider_key
    run.model_key = model_key
    run.provider_model_name = provider_model_name
    run.prompt_key = prompt_key
    run.prompt_version = prompt_version
    run.prompt_hash = prompt_hash
    run.completed_at = _now()
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, *, organisation_id: str, workspace_id: str, run_id: str) -> EvaluationRun | None:
    statement = select(EvaluationRun).where(
        EvaluationRun.id == run_id,
        EvaluationRun.organisation_id == organisation_id,
        EvaluationRun.workspace_id == workspace_id,
    )
    return db.execute(statement).scalar_one_or_none()


def list_runs(db: Session, *, organisation_id: str, workspace_id: str, dataset_id: str | None = None, limit: int = 50) -> list[EvaluationRun]:
    statement = select(EvaluationRun).where(
        EvaluationRun.organisation_id == organisation_id,
        EvaluationRun.workspace_id == workspace_id,
    )
    if dataset_id is not None:
        statement = statement.where(EvaluationRun.dataset_id == dataset_id)
    statement = statement.order_by(EvaluationRun.created_at.desc()).limit(limit)
    return list(db.execute(statement).scalars().all())


# --- results ----------------------------------------------------------------


def create_result(db: Session, *, run_id: str, case: EvaluationCase, payload: dict) -> EvaluationResult:
    result = EvaluationResult(
        run_id=run_id,
        case_id=case.id,
        organisation_id=case.organisation_id,
        workspace_id=case.workspace_id,
        **payload,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def list_results_for_run(db: Session, *, run_id: str, only_failed: bool = False) -> list[EvaluationResult]:
    statement = select(EvaluationResult).where(EvaluationResult.run_id == run_id)
    if only_failed:
        statement = statement.where(EvaluationResult.passed.is_(False))
    statement = statement.order_by(EvaluationResult.created_at.asc())
    return list(db.execute(statement).scalars().all())


def get_result_for_case(db: Session, *, run_id: str, case_id: str) -> EvaluationResult | None:
    statement = select(EvaluationResult).where(EvaluationResult.run_id == run_id, EvaluationResult.case_id == case_id)
    return db.execute(statement).scalar_one_or_none()


def update_result(db: Session, *, result: EvaluationResult, updates: dict) -> EvaluationResult:
    for field, value in updates.items():
        setattr(result, field, value)
    db.commit()
    db.refresh(result)
    return result
