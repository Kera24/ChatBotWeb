from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.base import Base
from app.db.models import Widget, WidgetConfigurationRevision
from app.operations.staging_synthetic_widgets import bootstrap_synthetic_widgets, assert_staging_bootstrap_allowed


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session
    Base.metadata.drop_all(engine)


def test_staging_synthetic_bootstrap_rejects_production_and_missing_confirmation() -> None:
    with pytest.raises(RuntimeError):
        assert_staging_bootstrap_allowed({"APP_ENV": "production", "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP": "1"})
    with pytest.raises(RuntimeError):
        assert_staging_bootstrap_allowed({"APP_ENV": "pilot", "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP": "1"})
    with pytest.raises(RuntimeError):
        assert_staging_bootstrap_allowed({"APP_ENV": "staging"})
    assert_staging_bootstrap_allowed({"APP_ENV": "staging", "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP": "1"})


def test_staging_synthetic_bootstrap_idempotent_and_separated(db_session, tmp_path: Path) -> None:
    env = {"APP_ENV": "staging", "WIDGET_STAGING_SYNTHETIC_BOOTSTRAP": "1"}
    report_path = tmp_path / "synthetic-widgets.json"

    first = bootstrap_synthetic_widgets(db_session, env=env, report_path=report_path)
    second = bootstrap_synthetic_widgets(db_session, env=env, report_path=report_path)

    assert first["overall_status"] == "ready"
    assert second["overall_status"] == "ready"
    assert first["alpha"]["tenant_id"] != first["beta"]["tenant_id"]
    assert first["alpha"]["workspace_id"] != first["beta"]["workspace_id"]
    assert first["alpha"]["widget_id"] != first["beta"]["widget_id"]
    assert first["alpha"]["public_key"] != first["beta"]["public_key"]
    assert first["alpha"]["allowed_origin"] != first["beta"]["allowed_origin"]
    assert second["alpha"]["public_key"] == first["alpha"]["public_key"]
    assert second["beta"]["public_key"] == first["beta"]["public_key"]
    assert second["alpha"]["published_revision"] == first["alpha"]["published_revision"]
    assert second["beta"]["published_revision"] == first["beta"]["published_revision"]
    assert first["alpha"]["knowledge_ready"] is True
    assert first["beta"]["knowledge_ready"] is True

    widgets = db_session.execute(select(Widget)).scalars().all()
    assert len(widgets) == 2
    for widget in widgets:
        assert widget.operational_status == "enabled"
        assert widget.pilot_status == "approved"
        assert widget.active_published_revision_id is not None

    alpha_revision = db_session.get(WidgetConfigurationRevision, first["alpha"]["published_revision"])
    beta_revision = db_session.get(WidgetConfigurationRevision, first["beta"]["published_revision"])
    assert alpha_revision is not None
    assert beta_revision is not None
    assert alpha_revision.knowledge_scope_json
    assert beta_revision.knowledge_scope_json
    assert alpha_revision.knowledge_scope_json != beta_revision.knowledge_scope_json

    text = report_path.read_text(encoding="utf-8")
    assert "DATABASE_URL" not in text
    assert "session_token" not in text
    assert "signing" not in text.lower()
    assert "connection" not in text.lower()
    assert "Alpha synthetic staging knowledge label" not in text
    assert "Beta synthetic staging knowledge label" not in text
