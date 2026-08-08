from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import ChatMessage, ChatSession, Membership, Organisation, User, Workspace
from app.operations import production_signal_scan


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'signal-scan-cli.db'}"


@pytest.fixture()
def db_session(db_url: str):
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant_with_fallback(db: Session, *, suffix: str) -> tuple[Organisation, Workspace, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    widget = create_widget(db, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id)

    chat_session = ChatSession(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, channel="widget", status="active", started_at=datetime.now(timezone.utc))
    db.add(chat_session)
    db.flush()
    db.add(ChatMessage(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, conversation_id=chat_session.id, role="user", content="How do I merge accounts?", sequence_number=1, created_at=datetime.now(timezone.utc)))
    db.add(ChatMessage(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, conversation_id=chat_session.id, role="assistant", content="I don't know.", sequence_number=2, answer_state="fallback", created_at=datetime.now(timezone.utc)))
    db.commit()
    return organisation, workspace, widget.id


def test_scan_cli_creates_candidate_and_exits_zero(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, widget_id = _seed_tenant_with_fallback(db_session, suffix="scan-cli")

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(production_signal_scan, "SessionLocal", sessionmaker(bind=engine))

    exit_code = production_signal_scan.main(["--organisation", organisation.id, "--workspace", workspace.id, "--assistant", widget_id, "--since-hours", "24"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "created 1" in output


def test_scan_cli_dry_run_does_not_persist(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, widget_id = _seed_tenant_with_fallback(db_session, suffix="scan-cli-dry")

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(production_signal_scan, "SessionLocal", sessionmaker(bind=engine))

    exit_code = production_signal_scan.main(["--organisation", organisation.id, "--workspace", workspace.id, "--assistant", widget_id, "--dry-run"])

    assert exit_code == 0
    assert "[dry-run]" in capsys.readouterr().out

    from app.db.models import EvaluationCandidate
    from sqlalchemy import select

    remaining = db_session.execute(select(EvaluationCandidate)).scalars().all()
    assert remaining == []


def test_scan_cli_returns_2_for_unknown_workspace(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, _workspace, widget_id = _seed_tenant_with_fallback(db_session, suffix="scan-cli-missing")

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(production_signal_scan, "SessionLocal", sessionmaker(bind=engine))

    exit_code = production_signal_scan.main(["--organisation", organisation.id, "--workspace", "does-not-exist", "--assistant", widget_id])

    assert exit_code == 2
    assert "not found" in capsys.readouterr().err
