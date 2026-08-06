from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import (
    Chunk,
    Document,
    DocumentVersion,
    EvaluationCase,
    EvaluationDataset,
    Membership,
    Organisation,
    User,
    Workspace,
)
from app.ai.guardrails.evidence_sufficiency import EvidenceSufficiencyVerdict, RequestedFact
from app.ai.guardrails.reason_codes import GuardrailReasonCode
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.operations import eval_launch, eval_report, eval_run


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'eval-cli.db'}"


@pytest.fixture()
def db_session(db_url: str):
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "eval-cli-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed_document(db: Session, *, organisation_id: str, workspace_id: str, key: str, title: str, content: str) -> str:
    document = Document(organisation_id=organisation_id, workspace_id=workspace_id, title=title, source_type="txt", source_key=f"{key}.txt", status="ready")
    db.add(document)
    db.flush()
    version = DocumentVersion(organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, version_number=1, checksum=f"checksum-{key}", processing_status="ready")
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    chunk = Chunk(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()),
        source_type="txt", source_title=title, status="ready",
        embedding_provider="local-mock", embedding_model="eval-cli-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    )
    db.add(chunk)
    db.commit()
    return document.id


def _seed_tenant(db: Session, *, suffix: str) -> tuple[Organisation, Workspace, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation, workspace, user.id


def _make_dataset_and_case(db: Session, *, organisation: Organisation, workspace: Workspace, widget_id: str, document_id: str) -> EvaluationDataset:
    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="CLI test dataset", version="1", status="active")
    db.add(dataset)
    db.flush()
    db.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="When do applications close?", expected_document_ids=[document_id],
        expected_answerability="answerable", category="answerable_factual",
    ))
    db.commit()
    db.refresh(dataset)
    return dataset


def test_eval_run_cli_executes_and_prints_text_report(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="cli-run")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_and_case(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_run, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_run.main([
        "--dataset", dataset.id, "--assistant", widget.id,
        "--organisation", organisation.id, "--workspace", workspace.id,
        "--mode", "mock", "--format", "text",
    ])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Evaluation run" in output
    assert "Cases:            1" in output


def test_eval_run_cli_returns_2_for_unknown_dataset(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, _user_id = _seed_tenant(db_session, suffix="cli-missing")

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_run, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_run.main([
        "--dataset", "does-not-exist", "--assistant", "does-not-exist",
        "--organisation", organisation.id, "--workspace", workspace.id,
    ])

    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_eval_report_cli_prints_json_report(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="cli-report")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_and_case(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    run = run_evaluation(
        db_session, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id,
        widget_id=widget.id, options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_report, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_report.main([
        "--run", run.id, "--organisation", organisation.id, "--workspace", workspace.id, "--format", "json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == run.id
    assert payload["summary"]["total_cases"] == 1
    assert "gate" in payload


def test_eval_report_cli_unknown_run_returns_2(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, _user_id = _seed_tenant(db_session, suffix="cli-report-missing")

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_report, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_report.main([
        "--run", "does-not-exist", "--organisation", organisation.id, "--workspace", workspace.id,
    ])

    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_eval_report_cli_gate_flag_fails_exit_code_on_hard_failure(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="cli-gate")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})

    # The evidence-sufficiency guardrail (app.ai.guardrails.evidence_sufficiency)
    # now reliably catches an "unanswerable" case against an in-scope but
    # unrelated document regardless of question phrasing - which is the whole
    # point of that guardrail, but it means this test can no longer force a
    # hard failure through question wording alone. This test's actual purpose
    # is the CLI gate/exit-code plumbing (not guardrail correctness, which has
    # its own dedicated tests in tests/test_guardrails.py), so bypass the
    # guardrail directly to deterministically simulate "the model answered
    # when it should have fallen back" - the exact hard-failure condition the
    # gate must report on.
    monkeypatch.setattr(
        "app.ai.rag_orchestrator.verify_evidence_sufficiency",
        lambda **kwargs: EvidenceSufficiencyVerdict(
            sufficient=True,
            reason_code=GuardrailReasonCode.SUFFICIENT_EVIDENCE,
            requested_fact=RequestedFact(entities=(), attribute_type=None, off_topic_likely=False),
            chunk_outcomes=(),
        ),
    )
    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Gate failure dataset", version="1", status="active")
    db_session.add(dataset)
    db_session.flush()
    db_session.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="What is the weather like today?", expected_answerability="unanswerable", category="unanswerable",
    ))
    db_session.commit()
    db_session.refresh(dataset)

    run = run_evaluation(
        db_session, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id,
        widget_id=widget.id, options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )
    assert run.hard_failure_cases == 1

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_report, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_report.main([
        "--run", run.id, "--organisation", organisation.id, "--workspace", workspace.id, "--gate",
    ])

    assert exit_code == 1
    assert "FAILED" in capsys.readouterr().out


def test_eval_report_cli_baseline_comparison(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="cli-baseline")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_and_case(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    baseline_run = run_evaluation(
        db_session, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id,
        widget_id=widget.id, options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )
    candidate_run = run_evaluation(
        db_session, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id,
        widget_id=widget.id, options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_report, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_report.main([
        "--run", candidate_run.id, "--organisation", organisation.id, "--workspace", workspace.id,
        "--baseline", baseline_run.id, "--format", "json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == candidate_run.id


def test_eval_launch_cli_runs_end_to_end_against_temp_database(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = eval_launch.main(["--format", "text"])

    output = capsys.readouterr().out
    assert "Evaluation run" in output
    assert "Category breakdown:" in output
    # The launch fixture includes unanswerable/fallback_expected cases that hard-fail
    # against the current retrieval pipeline (no similarity-confidence threshold) -
    # this is a documented, pre-existing product limitation, not an eval bug.
    assert exit_code == 1
    assert "known,\npre-existing retrieval-pipeline characteristic" in output
