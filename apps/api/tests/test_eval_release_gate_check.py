from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.production_gate import evaluate_production_readiness
from app.operations import eval_release_gate_check
from app.repositories import evaluation_candidate_repository, evaluation_repository


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'release-gate-cli.db'}"


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
        "actual_answer": "answer", "answer_state": "answered", "retrieved_document_ids": [], "retrieved_chunk_ids": [],
        "citations_json": [], "latency_ms": 100, "prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20,
        "retrieval_metrics_json": {}, "answer_metrics_json": {"answer_produced": True}, "judge_scores_json": None,
        "passed": passed, "hard_failure": hard_failure, "failure_reasons_json": [] if passed else ["mismatch"], "error_message": None,
    }


def _completed_run(db: Session, *, organisation, workspace, widget_id: str, dataset, completed_at, hard_failure_cases: int = 0):
    run = evaluation_repository.create_run(
        db, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset=dataset, mode="mock",
        policy_snapshot={}, retrieval_settings=None, created_by=None,
    )
    run.status = "completed"
    run.completed_at = completed_at
    run.hard_failure_cases = hard_failure_cases
    db.commit()
    db.refresh(run)
    return run


def test_gate_fails_when_no_completed_run_exists(db_session: Session) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="gate-no-run")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="D", description=None, version="1", created_by=None
    )
    verdict = evaluate_production_readiness(db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset_id=dataset.id)
    assert verdict.passed is False
    assert any("no completed evaluation run" in reason for reason in verdict.reasons)


def test_gate_fails_on_hard_failures_in_latest_run(db_session: Session) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="gate-hard-failure")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="D", description=None, version="1", created_by=None
    )
    _completed_run(db_session, organisation=organisation, workspace=workspace, widget_id=widget_id, dataset=dataset, completed_at=datetime.now(timezone.utc), hard_failure_cases=2)

    verdict = evaluate_production_readiness(db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset_id=dataset.id)
    assert verdict.passed is False
    assert any("hard failure" in reason for reason in verdict.reasons)


def test_gate_fails_on_stale_baseline(db_session: Session) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="gate-stale")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="D", description=None, version="1", created_by=None
    )
    _completed_run(db_session, organisation=organisation, workspace=workspace, widget_id=widget_id, dataset=dataset, completed_at=datetime.now(timezone.utc) - timedelta(days=30))

    verdict = evaluate_production_readiness(db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset_id=dataset.id, max_baseline_age_days=7)
    assert verdict.passed is False
    assert any("stale" in reason or "baseline freshness" in reason for reason in verdict.reasons)


def test_gate_fails_when_dataset_version_changed_without_new_completed_run(db_session: Session) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="gate-stale-version")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="D", description=None, version="1", created_by=None
    )
    _completed_run(db_session, organisation=organisation, workspace=workspace, widget_id=widget_id, dataset=dataset, completed_at=datetime.now(timezone.utc))
    dataset.version = "2"
    db_session.commit()

    verdict = evaluate_production_readiness(db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset_id=dataset.id)
    assert verdict.passed is False
    assert any("dataset version" in reason for reason in verdict.reasons)


def test_gate_fails_when_accepted_promoted_case_still_fails(db_session: Session) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="gate-accepted-failing")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="D", description=None, version="1", created_by=None
    )
    case = evaluation_repository.create_case(
        db_session, dataset=dataset, question="q", reference_answer=None, expected_document_ids=None, expected_source_labels=None,
        expected_answerability="answerable", category="answerable_factual", tags=None, metadata_json=None,
    )
    run = _completed_run(db_session, organisation=organisation, workspace=workspace, widget_id=widget_id, dataset=dataset, completed_at=datetime.now(timezone.utc))
    evaluation_repository.create_result(db_session, run_id=run.id, case=case, payload=_result_payload(passed=False))

    candidate = evaluation_candidate_repository.create_candidate(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, signal_type="fallback", severity="medium",
        question="q", response=None, reason_code="fallback",
    )
    evaluation_candidate_repository.update_triage(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, candidate_id=candidate.id, actor_user_id=None, triage_status="accepted",
    )
    candidate.promoted_case_id = case.id
    candidate.dataset_destination_id = dataset.id
    db_session.commit()

    verdict = evaluate_production_readiness(db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset_id=dataset.id)
    assert verdict.passed is False
    assert any("still fails" in reason for reason in verdict.reasons)


def test_gate_passes_when_all_conditions_are_satisfied(db_session: Session) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="gate-pass")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="D", description=None, version="1", created_by=None
    )
    _completed_run(db_session, organisation=organisation, workspace=workspace, widget_id=widget_id, dataset=dataset, completed_at=datetime.now(timezone.utc))

    verdict = evaluate_production_readiness(db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, dataset_id=dataset.id)
    assert verdict.passed is True
    assert verdict.reasons == []


def test_cli_exits_1_when_gate_fails(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, widget_id = _seed_tenant(db_session, suffix="gate-cli")
    dataset = evaluation_repository.create_dataset(
        db_session, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="D", description=None, version="1", created_by=None
    )

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_release_gate_check, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_release_gate_check.main([
        "--dataset", dataset.id, "--assistant", widget_id, "--organisation", organisation.id, "--workspace", workspace.id, "--format", "json",
    ])
    assert exit_code == 1
    body = json.loads(capsys.readouterr().out)
    assert body["passed"] is False
