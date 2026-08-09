"""Tests for the alert-delivery CLI (app.operations.alert_dispatch_run) -
the lightweight scheduled/cron entry point that evaluates
app.observability.alerts.evaluate_alerts and delivers any triggered alerts.
Uses the guaranteed-to-trigger "zero_traffic" info-level alert (an empty
workspace has no AI traces in the trailing window) rather than seeding AI
trace fixtures, matching the CLI-test style of
tests/test_production_signal_scan_cli.py / tests/test_eval_release_gate_check.py."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.operations import alert_dispatch_run


@contextmanager
def _settings_override(**overrides: Any) -> Iterator[None]:
    originals = {name: getattr(settings, name) for name in overrides}
    for name, value in overrides.items():
        object.__setattr__(settings, name, value)
    try:
        yield
    finally:
        for name, value in originals.items():
            object.__setattr__(settings, name, value)


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'alert-dispatch-cli.db'}"


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


def test_cli_returns_2_for_unknown_workspace(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, _workspace, _widget_id = _seed_tenant(db_session, suffix="alert-cli-missing")
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(alert_dispatch_run, "SessionLocal", sessionmaker(bind=engine))

    exit_code = alert_dispatch_run.main(["--organisation", organisation.id, "--workspace", "does-not-exist"])

    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_cli_returns_2_for_non_positive_window(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    organisation, workspace, _widget_id = _seed_tenant(db_session, suffix="alert-cli-window")
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(alert_dispatch_run, "SessionLocal", sessionmaker(bind=engine))

    exit_code = alert_dispatch_run.main(["--organisation", organisation.id, "--workspace", workspace.id, "--window-hours", "0"])

    assert exit_code == 2
    assert "Refusing to run" in capsys.readouterr().err


def test_cli_dry_run_reports_zero_traffic_alert_without_delivering(
    db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    organisation, workspace, _widget_id = _seed_tenant(db_session, suffix="alert-cli-dry")
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(alert_dispatch_run, "SessionLocal", sessionmaker(bind=engine))

    exit_code = alert_dispatch_run.main(["--organisation", organisation.id, "--workspace", workspace.id, "--dry-run"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "[dry-run]" in output
    assert "zero_traffic" in output


def test_cli_delivers_zero_traffic_alert_when_min_severity_allows_it(
    db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    organisation, workspace, _widget_id = _seed_tenant(db_session, suffix="alert-cli-deliver")
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(alert_dispatch_run, "SessionLocal", sessionmaker(bind=engine))

    with _settings_override(ALERT_PROVIDER="dev", ALERT_MIN_SEVERITY="info", ALERT_COOLDOWN_STATE_PATH=str(tmp_path / "cooldown.json")):
        exit_code = alert_dispatch_run.main(["--organisation", organisation.id, "--workspace", workspace.id])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "delivered 1" in output


def test_cli_skips_delivery_below_default_min_severity(
    db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    organisation, workspace, _widget_id = _seed_tenant(db_session, suffix="alert-cli-skip-severity")
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(alert_dispatch_run, "SessionLocal", sessionmaker(bind=engine))

    with _settings_override(ALERT_PROVIDER="dev", ALERT_MIN_SEVERITY="warning", ALERT_COOLDOWN_STATE_PATH=str(tmp_path / "cooldown.json")):
        exit_code = alert_dispatch_run.main(["--organisation", organisation.id, "--workspace", workspace.id])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "delivered 0" in output
    assert "skipped 1 (below min severity)" in output


def test_cli_returns_2_when_provider_is_misconfigured(
    db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    organisation, workspace, _widget_id = _seed_tenant(db_session, suffix="alert-cli-misconfigured")
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(alert_dispatch_run, "SessionLocal", sessionmaker(bind=engine))

    with _settings_override(ALERT_PROVIDER="slack", ALERT_MIN_SEVERITY="info", SLACK_WEBHOOK_URL=""):
        exit_code = alert_dispatch_run.main(["--organisation", organisation.id, "--workspace", workspace.id])

    assert exit_code == 2
    assert "misconfigured" in capsys.readouterr().err
