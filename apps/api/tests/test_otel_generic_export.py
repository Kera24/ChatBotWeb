from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import settings
from app.operations.telemetry import configure_observability


def _reset_env(**overrides: str) -> dict[str, str]:
    original = {
        "AZURE_MONITOR_OPEN_TELEMETRY_ENABLED": settings.AZURE_MONITOR_OPEN_TELEMETRY_ENABLED,
        "APPLICATIONINSIGHTS_CONNECTION_STRING": settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
        "OTEL_ENABLED": settings.OTEL_ENABLED,
        "OTEL_EXPORTER_OTLP_ENDPOINT": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        "OTEL_CONSOLE_EXPORT": settings.OTEL_CONSOLE_EXPORT,
    }
    for key, value in {
        "AZURE_MONITOR_OPEN_TELEMETRY_ENABLED": "false",
        "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
        "OTEL_ENABLED": "false",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "",
        "OTEL_CONSOLE_EXPORT": "false",
        **overrides,
    }.items():
        object.__setattr__(settings, key, value)
    return original


def _restore_env(original: dict[str, str]) -> None:
    for key, value in original.items():
        object.__setattr__(settings, key, value)


def test_otel_disabled_is_a_safe_noop() -> None:
    original = _reset_env()
    try:
        app = FastAPI()
        configure_observability(app)
        assert app.state.telemetry_enabled is False
    finally:
        _restore_env(original)


def test_otel_enabled_without_endpoint_starts_in_local_no_export_mode() -> None:
    original = _reset_env(OTEL_ENABLED="true")
    try:
        app = FastAPI()
        configure_observability(app)  # must not raise
        assert app.state.telemetry_enabled is False
    finally:
        _restore_env(original)


def test_otel_console_export_mode_starts_cleanly() -> None:
    original = _reset_env(OTEL_ENABLED="true", OTEL_CONSOLE_EXPORT="true")
    try:
        app = FastAPI()
        configure_observability(app)
        assert app.state.telemetry_enabled is True
    finally:
        _restore_env(original)


def test_otel_enabled_with_unreachable_endpoint_does_not_crash_startup() -> None:
    original = _reset_env(OTEL_ENABLED="true", OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:1/v1/traces")
    try:
        app = FastAPI()
        configure_observability(app)  # exporter creation/instrumentation must not raise even for a bad endpoint
    finally:
        _restore_env(original)


def test_otel_enabled_with_malformed_endpoint_does_not_crash_startup() -> None:
    # The OTLP exporter does not validate the endpoint URL eagerly - a bad
    # value only ever fails inside BatchSpanProcessor's background export
    # thread (per-request behavior is never affected). This test only
    # asserts that constructing it doesn't crash app startup.
    original = _reset_env(OTEL_ENABLED="true", OTEL_EXPORTER_OTLP_ENDPOINT="not a url")
    try:
        app = FastAPI()
        configure_observability(app)  # must not raise
    finally:
        _restore_env(original)


def test_both_azure_and_generic_otel_configured_prefers_azure_and_warns(caplog: "logging.LogCaptureFixture") -> None:
    original = _reset_env(
        AZURE_MONITOR_OPEN_TELEMETRY_ENABLED="true",
        APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=fake;IngestionEndpoint=https://example.test",
        OTEL_ENABLED="true",
    )
    telemetry_logger = logging.getLogger("chatbotweb.telemetry")
    # A prior test that invokes an actual Alembic command (e.g.
    # test_alembic_compat.py) triggers alembic.ini's logging.config.fileConfig,
    # which by default disables every "foreign" logger process-wide
    # (disable_existing_loggers=True) - a real Python logging.config gotcha,
    # not anything app code controls, and one that never occurs in
    # production (a real Alembic invocation runs in its own separate CLI
    # process, not alongside the running app). Explicitly re-enable this
    # logger so the assertion below is resilient to pytest run order/history.
    was_disabled = telemetry_logger.disabled
    telemetry_logger.disabled = False
    try:
        app = FastAPI()
        with caplog.at_level(logging.WARNING, logger="chatbotweb.telemetry"):
            configure_observability(app)
        assert any("Azure Monitor takes precedence" in message for message in caplog.messages)
        # Azure packages are not installed in this environment (see
        # app.operations.telemetry.configure_azure_monitor's own defensive
        # try/except) so export stays disabled either way, but the
        # precedence decision itself must never raise or attempt the
        # generic OTel path too.
        assert app.state.telemetry_enabled is False
    finally:
        telemetry_logger.disabled = was_disabled
        _restore_env(original)
