from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, EvaluationCase, EvaluationDataset, EvaluationRun, Membership, Organisation, User, Workspace
from app.operations import eval_focused_run


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'eval-focused-cli.db'}"


@pytest.fixture()
def db_session(db_url: str):
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "eval-focused-cli-test")
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
    db.add(Chunk(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()),
        source_type="txt", source_title=title, status="ready",
        embedding_provider="local-mock", embedding_model="eval-focused-cli-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    ))
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


def test_focused_run_defaults_to_production_fed_cases_only(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="focused-default")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})

    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Focused dataset", version="1", status="active")
    db_session.add(dataset)
    db_session.flush()
    production_case = EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="When do applications close?", expected_document_ids=[document_id],
        expected_answerability="answerable", category="answerable_factual", source_candidate_id="candidate-1",
    )
    hand_authored_case = EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="What is the weather?", expected_answerability="unanswerable", category="unanswerable",
    )
    db_session.add_all([production_case, hand_authored_case])
    db_session.commit()

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_focused_run, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_focused_run.main([
        "--dataset", dataset.id, "--assistant", widget.id, "--organisation", organisation.id, "--workspace", workspace.id, "--format", "json",
    ])
    assert exit_code == 0

    runs = db_session.execute(select(EvaluationRun).where(EvaluationRun.dataset_id == dataset.id)).scalars().all()
    assert len(runs) == 1
    assert runs[0].total_cases == 1
    assert runs[0].trigger_source == "focused"


def test_focused_run_with_no_production_fed_cases_exits_2(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="focused-empty")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id)

    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Empty focused dataset", version="1", status="active")
    db_session.add(dataset)
    db_session.flush()
    db_session.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="What is the weather?", expected_answerability="unanswerable", category="unanswerable",
    ))
    db_session.commit()

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_focused_run, "SessionLocal", sessionmaker(bind=engine))

    exit_code = eval_focused_run.main(["--dataset", dataset.id, "--assistant", widget.id, "--organisation", organisation.id, "--workspace", workspace.id])
    assert exit_code == 2
    assert "No production-fed cases" in capsys.readouterr().err
