from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.ai.rag_orchestrator import RAGOrchestrator
from app.core.config import settings
from app.db.base import Base
from app.db.models import (
    ChatMessage,
    ChatSession,
    Chunk,
    Citation,
    Document,
    DocumentVersion,
    EvaluationCase,
    EvaluationDataset,
    Membership,
    Organisation,
    ReviewAnnotation,
    User,
    Workspace,
)
from app.evaluation.categories import Answerability, CaseCategory
from app.evaluation.engine import EmptyDatasetError, EvaluationRunOptions, LiveModeNotConfiguredError, run_evaluation
from app.repositories.evaluation_repository import list_results_for_run


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'eval-engine.db'}"


@pytest.fixture()
def db_session(db_url: str):
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "eval-engine-test")
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
        embedding_provider="local-mock", embedding_model="eval-engine-test", embedding_dimension=8,
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
    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="Engine test dataset", version="1", status="active")
    db.add(dataset)
    db.flush()
    db.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="When do applications close?", expected_document_ids=[document_id],
        expected_answerability=Answerability.ANSWERABLE.value, category=CaseCategory.ANSWERABLE_FACTUAL.value,
    ))
    db.commit()
    db.refresh(dataset)
    return dataset


def test_run_evaluation_executes_mock_provider_and_scores_case(db_session: Session, db_url: str) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="mock")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_and_case(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    run = run_evaluation(
        db_session,
        dataset=dataset,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )

    assert run.status == "completed"
    assert run.total_cases == 1
    assert run.passed_cases == 1
    assert run.model_key == "mock-grounded-answer"
    assert run.provider_key == "mock"

    results = list_results_for_run(db_session, run_id=run.id)
    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].answer_state == "answered"
    assert results[0].retrieval_metrics_json["expected_document_retrieved"] is True


def test_run_evaluation_does_not_pollute_real_conversation_tables(db_session: Session, db_url: str) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="pollution")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_and_case(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    run_evaluation(
        db_session,
        dataset=dataset,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )

    assert db_session.execute(select(ChatMessage)).scalars().all() == []
    assert db_session.execute(select(ChatSession)).scalars().all() == []
    assert db_session.execute(select(Citation)).scalars().all() == []
    assert db_session.execute(select(ReviewAnnotation)).scalars().all() == []


def test_run_evaluation_continues_after_an_individual_case_failure(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="partial")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})

    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Partial failure dataset", version="1", status="active")
    db_session.add(dataset)
    db_session.flush()
    db_session.add_all([
        EvaluationCase(dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id, question="Q1", expected_document_ids=[document_id], expected_answerability="answerable", category="answerable_factual"),
        EvaluationCase(dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id, question="Q2", expected_document_ids=[document_id], expected_answerability="answerable", category="answerable_factual"),
        EvaluationCase(dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id, question="Q3", expected_document_ids=[document_id], expected_answerability="answerable", category="answerable_factual"),
    ])
    db_session.commit()
    db_session.refresh(dataset)

    original_answer = RAGOrchestrator.answer
    call_count = {"n": 0}

    def flaky_answer(self, request):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated unexpected engine error")
        return original_answer(self, request)

    monkeypatch.setattr(RAGOrchestrator, "answer", flaky_answer)

    run = run_evaluation(
        db_session,
        dataset=dataset,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )

    assert run.status == "completed"
    assert run.total_cases == 3
    assert run.failed_cases == 1
    assert run.passed_cases == 2

    results = list_results_for_run(db_session, run_id=run.id)
    failed = [r for r in results if not r.passed]
    assert len(failed) == 1
    assert "unexpected_engine_error" in (failed[0].failure_reasons_json or [])
    assert "RuntimeError" not in (failed[0].error_message or "") or "simulated" in (failed[0].error_message or "")


def test_run_evaluation_enforces_case_timeout(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="timeout")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_and_case(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    original_answer = RAGOrchestrator.answer

    def slow_answer(self, request):
        time.sleep(0.5)
        return original_answer(self, request)

    monkeypatch.setattr(RAGOrchestrator, "answer", slow_answer)

    run = run_evaluation(
        db_session,
        dataset=dataset,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", case_timeout_seconds=0.05, shadow_database_url=db_url),
    )

    assert run.status == "completed"
    results = list_results_for_run(db_session, run_id=run.id)
    assert results[0].passed is False
    assert "case_timeout" in (results[0].failure_reasons_json or [])


def test_run_evaluation_raises_for_empty_dataset(db_session: Session, db_url: str) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="empty")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Empty dataset", version="1", status="active")
    db_session.add(dataset)
    db_session.commit()

    with pytest.raises(EmptyDatasetError):
        run_evaluation(
            db_session,
            dataset=dataset,
            organisation_id=organisation.id,
            workspace_id=workspace.id,
            widget_id=widget.id,
            options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
        )


def test_run_evaluation_requires_explicit_ai_core_for_live_mode(db_session: Session, db_url: str) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="live")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_and_case(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    with pytest.raises(LiveModeNotConfiguredError):
        run_evaluation(
            db_session,
            dataset=dataset,
            organisation_id=organisation.id,
            workspace_id=workspace.id,
            widget_id=widget.id,
            options=EvaluationRunOptions(mode="live", shadow_database_url=db_url),
        )


def test_cross_assistant_leakage_case_passes_when_isolation_holds(db_session: Session, db_url: str) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="primary")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})

    foreign_organisation, foreign_workspace, foreign_user_id = _seed_tenant(db_session, suffix="foreign")
    foreign_widget = create_widget(db_session, organisation_id=foreign_organisation.id, workspace_id=foreign_workspace.id, display_name="Foreign Assistant", environment="development", actor_user_id=foreign_user_id)

    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Isolation dataset", version="1", status="active")
    db_session.add(dataset)
    db_session.flush()
    db_session.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="What does the other tenant's assistant know?", expected_answerability="unanswerable",
        category=CaseCategory.CROSS_ASSISTANT_LEAKAGE.value,
        metadata_json={"cross_tenant_attempt": {"widget_id": foreign_widget.id}},
    ))
    db_session.commit()
    db_session.refresh(dataset)

    run = run_evaluation(
        db_session,
        dataset=dataset,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url),
    )

    assert run.status == "completed"
    assert run.hard_failure_cases == 0
    results = list_results_for_run(db_session, run_id=run.id)
    assert results[0].passed is True
    assert results[0].hard_failure is False
