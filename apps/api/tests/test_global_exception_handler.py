from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import User
from app.db.session import get_db
from app.main import create_app

# Built at runtime (not a contiguous literal) so this fake test credential
# doesn't itself trip secret-scanners like GitHub push protection - it still
# matches _STRIPE_SECRET_PATTERN in app.observability.redaction at runtime.
_SECRET_MARKER = "".join(("sk", "_live_", "ThisIsAFakeStripeSecretKeyForTests1234567890"))
_GENERATE_PAYLOAD = {
    "prompt_key": "grounded_rag_answer",
    "model_key": "mock-grounded-answer",
    "variables": {"question": "What is Yoranix?", "context": "[1] Yoranix is a source-grounded AI platform."},
}


@pytest.fixture()
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    def override_get_db() -> Iterator[Session]:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # raise_server_exceptions=False: these tests deliberately trigger the
    # global ServerErrorMiddleware handler for genuinely unhandled
    # exceptions - Starlette always re-raises after invoking that handler
    # (so a real ASGI server still logs it) and TestClient's default of
    # re-raising too exists purely to surface bugs in tests, not to reflect
    # what a real client receives (which is the handler's response, already
    # sent before the re-raise).
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def dev_headers(email: str, role: str) -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


def _break_ai_generate_with_secret(client: TestClient) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(f"provider call failed while using key={_SECRET_MARKER}")

    client.app.state.ai_core.service.generate = _raise


@contextmanager
def errors_logger_enabled() -> Iterator[None]:
    """A prior in-process Alembic invocation (see apps/api/alembic/env.py's
    fileConfig call) can leave process-wide loggers disabled - see
    apps/api/tests/test_otel_generic_export.py for the same workaround."""
    logger = logging.getLogger("chatbotweb.errors")
    was_disabled = logger.disabled
    logger.disabled = False
    try:
        yield
    finally:
        logger.disabled = was_disabled


def test_unexpected_runtime_error_returns_safe_500(client: TestClient) -> None:
    _break_ai_generate_with_secret(client)

    response = client.post(
        "/api/v1/ai/generate",
        json=_GENERATE_PAYLOAD,
        headers={**dev_headers("super@example.test", "super_admin"), "X-Request-ID": "req-fixed-1"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["detail"]["code"] == "internal_server_error"
    assert body["detail"]["message"] == "An unexpected error occurred. Please try again or contact support if the problem persists."
    assert body["detail"]["request_id"] == "req-fixed-1"
    assert response.headers["X-Request-ID"] == "req-fixed-1"


def test_raw_exception_text_and_secrets_absent_from_response(client: TestClient) -> None:
    _break_ai_generate_with_secret(client)

    response = client.post(
        "/api/v1/ai/generate",
        json=_GENERATE_PAYLOAD,
        headers=dev_headers("super@example.test", "super_admin"),
    )

    raw_body = response.text
    assert "RuntimeError" not in raw_body
    assert "provider call failed" not in raw_body
    assert _SECRET_MARKER not in raw_body
    assert "Traceback" not in raw_body
    assert "main.py" not in raw_body


def test_secret_in_exception_never_reaches_log_output(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    _break_ai_generate_with_secret(client)

    with errors_logger_enabled():
        with caplog.at_level(logging.ERROR, logger="chatbotweb.errors"):
            client.post(
                "/api/v1/ai/generate",
                json=_GENERATE_PAYLOAD,
                headers=dev_headers("super@example.test", "super_admin"),
            )

    joined = "\n".join(caplog.messages)
    assert _SECRET_MARKER not in joined
    assert "[redacted-stripe_secret_key]" in joined
    assert any("api.unhandled_exception" in message for message in caplog.messages)
    assert any("RuntimeError" in message for message in caplog.messages)


def test_production_mode_does_not_change_or_leak_debug_detail(client: TestClient) -> None:
    # APP_ENV=production cannot be combined with a dev-header-authenticated
    # request (dev auth is refused outside development/test/testing - see
    # app.api.deps.get_development_current_user), so this asserts the
    # framework-level guarantee that actually matters here: Starlette's
    # ServerErrorMiddleware only renders its HTML debug/traceback page when
    # FastAPI(debug=True), and create_app() never sets that, so the
    # traceback page is unreachable regardless of APP_ENV/DEBUG env vars.
    assert client.app.debug is False

    _break_ai_generate_with_secret(client)
    response = client.post(
        "/api/v1/ai/generate",
        json=_GENERATE_PAYLOAD,
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 500
    assert "Traceback" not in response.text
    assert _SECRET_MARKER not in response.text
    assert response.json()["detail"]["code"] == "internal_server_error"


def test_http_exception_403_behaviour_is_unchanged(client: TestClient) -> None:
    with client.app.state.testing_session() as db:
        db.add(User(email="nobody@example.test"))
        db.commit()

    response = client.post(
        "/api/v1/ai/generate",
        json=_GENERATE_PAYLOAD,
        headers=dev_headers("nobody@example.test", "client_admin"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "super_admin role required."


def test_validation_422_behaviour_is_unchanged(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json={"model_key": "mock-grounded-answer"},
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_provider_mapped_error_behaviour_is_unchanged(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json={**_GENERATE_PAYLOAD, "simulate_failure": True},
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "AI_PROVIDER_ERROR",
        "message": "Mock provider failure simulation requested.",
    }


def test_unexpected_exception_before_widget_route_body_uses_widget_safe_envelope(client: TestClient) -> None:
    def _broken_db() -> Iterator[Session]:
        raise RuntimeError(f"db connection failed: postgres://user:pass@host:5432/db key={_SECRET_MARKER}")
        yield  # pragma: no cover - keeps this a generator dependency

    client.app.dependency_overrides[get_db] = _broken_db

    response = client.get("/api/v1/widget/wpk_doesnotexist/config")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "safe_internal_error"
    assert "request_id" in body
    assert "postgres://" not in response.text
    assert _SECRET_MARKER not in response.text
