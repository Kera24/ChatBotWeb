from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import EvaluationCase, EvaluationDataset, EvaluationRegressionReport, Membership, Organisation, User, Workspace
from app.access.widget_admin.service import create_widget
from app.operations import eval_regression_report
from app.repositories import evaluation_repository


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'eval-regression-cli.db'}"


@pytest.fixture()
def db_session(db_url: str):
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db: Session, *, suffix: str) -> tuple[Organisation, Workspace, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    widget = create_widget(db, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id)
    return organisation, workspace, widget.id


def _result_payload(*, passed: bool, hard_failure: bool = False) -> dict:
    return {
        "actual_answer": "answer" if passed else None,
        "answer_state": "answered" if passed else "failed",
        "retrieved_document_ids": [],
        "retrieved_chunk_ids": [],
        "citations_json": [],
        "latency_ms": 100,
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "total_tokens": 20,
        "retrieval_metrics_json": {},
        "answer_metrics_json": {"answer_produced": True},
        "judge_scores_json": None,
        "passed": passed,
        "hard_failure": hard_failure,
        "failure_reasons_json": [] if passed else ["mismatch"],
        "error_message": None,
    }


def test_regression_report_classifies_new_fixed_and_newly_failing_cases(
    db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="regression")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="Regression dataset", description=None, version="1", created_by=None
    )
    case_stable = evaluation_repository.create_case(
        db_session, dataset=dataset, question="stable question", reference_answer=None, expected_document_ids=None,
        expected_source_labels=None, expected_answerability="answerable", category="answerable_factual", tags=None, metadata_json=None,
    )
    case_to_be_fixed = evaluation_repository.create_case(
        db_session, dataset=dataset, question="was failing question", reference_answer=None, expected_document_ids=None,
        expected_source_labels=None, expected_answerability="answerable", category="answerable_factual", tags=None, metadata_json=None,
    )
    case_to_regress = evaluation_repository.create_case(
        db_session, dataset=dataset, question="was passing question", reference_answer=None, expected_document_ids=None,
        expected_source_labels=None, expected_answerability="answerable", category="answerable_factual", tags=None, metadata_json=None,
    )

    baseline_run = evaluation_repository.create_run(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset=dataset, mode="mock",
        policy_snapshot={}, retrieval_settings=None, created_by=None,
    )
    evaluation_repository.mark_run_started(db_session, run=baseline_run)
    evaluation_repository.create_result(db_session, run_id=baseline_run.id, case=case_stable, payload=_result_payload(passed=True))
    evaluation_repository.create_result(db_session, run_id=baseline_run.id, case=case_to_be_fixed, payload=_result_payload(passed=False))
    evaluation_repository.create_result(db_session, run_id=baseline_run.id, case=case_to_regress, payload=_result_payload(passed=True))
    evaluation_repository.mark_run_completed(
        db_session, run=baseline_run, status="completed", total_cases=3, passed_cases=2, failed_cases=1, hard_failure_cases=0,
        provider_key=None, model_key=None, provider_model_name=None, prompt_key=None, prompt_version=None, prompt_hash=None,
    )

    candidate_case_new = evaluation_repository.create_case(
        db_session, dataset=dataset, question="brand new question", reference_answer=None, expected_document_ids=None,
        expected_source_labels=None, expected_answerability="answerable", category="answerable_factual", tags=None, metadata_json=None,
    )
    candidate_run = evaluation_repository.create_run(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset=dataset, mode="mock",
        policy_snapshot={}, retrieval_settings=None, created_by=None,
    )
    evaluation_repository.mark_run_started(db_session, run=candidate_run)
    evaluation_repository.create_result(db_session, run_id=candidate_run.id, case=case_stable, payload=_result_payload(passed=True))
    evaluation_repository.create_result(db_session, run_id=candidate_run.id, case=case_to_be_fixed, payload=_result_payload(passed=True))
    evaluation_repository.create_result(db_session, run_id=candidate_run.id, case=case_to_regress, payload=_result_payload(passed=False))
    evaluation_repository.create_result(db_session, run_id=candidate_run.id, case=candidate_case_new, payload=_result_payload(passed=True))
    evaluation_repository.mark_run_completed(
        db_session, run=candidate_run, status="completed", total_cases=4, passed_cases=3, failed_cases=1, hard_failure_cases=0,
        provider_key=None, model_key=None, provider_model_name=None, prompt_key=None, prompt_version=None, prompt_hash=None,
    )

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_regression_report, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_regression_report.main([
        "--run", candidate_run.id, "--baseline-run", baseline_run.id, "--organisation", organisation.id, "--workspace", workspace.id, "--created-by", "system:test",
    ])
    assert exit_code == 0

    output = json.loads(capsys.readouterr().out)
    report = output["report"]
    assert report["new_cases"] == [candidate_case_new.id]
    assert report["fixed_cases"] == [case_to_be_fixed.id]
    assert report["newly_failing_cases"] == [case_to_regress.id]
    assert report["still_failing_cases"] == []

    persisted = db_session.query(EvaluationRegressionReport).filter_by(run_id=candidate_run.id).one()
    assert persisted.baseline_run_id == baseline_run.id
    assert persisted.created_by == "system:test"
