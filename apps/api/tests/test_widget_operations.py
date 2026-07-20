from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.observability.events import InMemoryAccessEventSink
from app.access.rate_limit.redis_store import InMemoryRateLimitStore
from app.api.deps import get_db
from app.db.base import Base
from app.main import create_app
from app.operations.alerts import validate_alert_policy
from app.operations.correlation import safe_request_id
from app.operations.logging import redact
from app.operations.metrics import InMemoryOperationalMetrics
from app.operations.rollback import build_rollback_plan
from app.operations.widget_controls import WidgetOperationalControls, evaluate_widget_access, parse_bool, parse_identifier_list
from test_public_widget_message_endpoint import create_public_session, post_message
from test_public_widget_session_endpoint import post_session, seed_widget

ORIGIN = "http://localhost:3000"


@pytest.fixture()
def operational_client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession
    app.state.public_widget_rate_limit_store = InMemoryRateLimitStore()
    app.state.public_widget_event_sink = InMemoryAccessEventSink()

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_liveness_and_readiness_are_safe_and_dependency_bounded(operational_client: TestClient) -> None:
    live = operational_client.get("/health/live")
    ready = operational_client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"] == {"database": "ok", "retrieval": "ok", "public_widget": "ok"}
    assert "DATABASE_URL" not in ready.text
    assert "mock-grounded-answer" not in ready.text


def test_readiness_fails_closed_when_database_check_fails() -> None:
    app = create_app()

    class BrokenDb:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("db unavailable")

    def override_get_db():
        yield BrokenDb()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["database"] == "failed"
    assert "db unavailable" not in response.text


def test_correlation_id_validation_replaces_invalid_values() -> None:
    assert safe_request_id("req-public-123") == "req-public-123"
    assert safe_request_id("bad value with spaces") != "bad value with spaces"
    assert safe_request_id("x" * 121) != "x" * 121
    assert "\n" not in safe_request_id("bad\nheader")


def test_redaction_removes_sensitive_operational_fields() -> None:
    value = redact(
        {
            "session_token": "pss_dev_abcdefghijklmnop.abcdefghijklmnopqrstuvwx",
            "authorization": "Bearer secret",
            "message": "customer text",
            "public_key": "wpk_dev_1234567890abcdef",
            "safe": "ok",
        }
    )

    rendered = json.dumps(value)
    assert "pss_dev_" not in rendered
    assert "Bearer secret" not in rendered
    assert "customer text" not in rendered
    assert "wpk_dev_1234567890abcdef" not in rendered
    assert value["safe"] == "ok"


def test_operational_config_parsing_and_policy_decisions() -> None:
    assert parse_bool("true", default=False) is True
    assert parse_bool("0", default=True) is False
    with pytest.raises(ValueError):
        parse_bool("maybe", default=True)
    assert parse_identifier_list("wpk_a,wpk_b") == frozenset({"wpk_a", "wpk_b"})
    with pytest.raises(ValueError):
        parse_identifier_list("wpk_a,wpk_a")

    assert evaluate_widget_access("wpk_a", controls=WidgetOperationalControls(), operation="config") is None
    assert evaluate_widget_access("wpk_a", controls=WidgetOperationalControls(public_widgets_enabled=False), operation="config").code == "temporarily_unavailable"
    assert evaluate_widget_access("wpk_a", controls=WidgetOperationalControls(public_widget_messages_enabled=False), operation="message").code == "temporarily_unavailable"
    assert evaluate_widget_access("wpk_a", controls=WidgetOperationalControls(pilot_enforcement_enabled=True, pilot_allowlist=frozenset({"wpk_b"})), operation="config").code == "invalid_widget"


def test_public_widget_pilot_allowlist_and_kill_switches(operational_client: TestClient) -> None:
    allowed_key = seed_widget(operational_client)
    denied_key = seed_widget(operational_client)
    operational_client.app.state.widget_operational_controls = WidgetOperationalControls(pilot_enforcement_enabled=True, pilot_allowlist=frozenset({allowed_key}))

    assert operational_client.get(f"/api/v1/widget/{allowed_key}/config", headers={"Origin": ORIGIN}).status_code == 200
    denied = operational_client.get(f"/api/v1/widget/{denied_key}/config", headers={"Origin": ORIGIN})
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "invalid_widget"

    operational_client.app.state.widget_operational_controls = WidgetOperationalControls(public_widgets_enabled=False)
    disabled = operational_client.get(f"/api/v1/widget/{allowed_key}/config", headers={"Origin": ORIGIN, "X-Request-ID": "req-disabled"})
    session_disabled = post_session(operational_client, allowed_key, headers={"X-Request-ID": "req-disabled-session"})
    assert disabled.status_code == 503
    assert disabled.headers["x-request-id"] == "req-disabled"
    assert session_disabled.status_code == 503


def test_global_message_kill_switch_blocks_existing_sessions(operational_client: TestClient) -> None:
    public_key = seed_widget(operational_client)
    token = create_public_session(operational_client, public_key)

    operational_client.app.state.widget_operational_controls = WidgetOperationalControls(public_widget_messages_enabled=False)
    response = post_message(operational_client, public_key, token, key="idem-message-disabled")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "temporarily_unavailable"


def test_operational_metrics_and_logs_are_safe(operational_client: TestClient) -> None:
    public_key = seed_widget(operational_client)
    metrics = InMemoryOperationalMetrics()
    stream = io.StringIO()
    logger = logging.getLogger("widget-ops-test")
    logger.handlers = []
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    operational_client.app.state.public_widget_operational_metrics = metrics
    operational_client.app.state.public_widget_operational_logger = logger

    response = operational_client.get(f"/api/v1/widget/{public_key}/config", headers={"Origin": ORIGIN, "X-Request-ID": "req-ops-log"})

    assert response.status_code == 200
    snapshot = metrics.snapshot()
    assert snapshot["public_widget.config.success"] >= 1
    logs = stream.getvalue()
    assert "req-ops-log" in logs
    assert public_key not in logs
    assert "session_token" not in logs
    assert "What are" not in logs


def test_alert_policy_and_rollback_plan_validation(tmp_path) -> None:
    alerts = validate_alert_policy(Path(__file__).resolve().parents[3] / "deployment" / "widget" / "alerts.json")
    assert any(alert["severity"] == "critical" for alert in alerts)

    current = tmp_path / "current.json"
    target = tmp_path / "target.json"
    current.write_text(json.dumps({"sdk_version": "1.0.1", "protocol_major": 1, "api_version": "v1"}), encoding="utf-8")
    target.write_text(
        json.dumps(
            {
                "sdk_version": "1.0.0",
                "protocol_major": 1,
                "api_version": "v1",
                "major_alias_path": "/widget-sdk/v1/loader.js",
                "immutable_loader_path": "/widget-sdk/v1.0.0/loader.js",
                "build_commit": "abc123",
            }
        ),
        encoding="utf-8",
    )
    plan = build_rollback_plan(current, target)
    assert plan["mode"] == "dry_run"
    assert plan["to_sdk_version"] == "1.0.0"


