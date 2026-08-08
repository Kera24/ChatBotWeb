"""Tests for the transactional email provider abstraction (P0-2 of the
launch readiness review): DevEmailProvider, ResendEmailProvider, and
app.email.dependencies.build_email_provider's selection/validation policy.
Deterministic, no network required - Resend calls are intercepted by
monkeypatching resend.Emails.send."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Iterator

import pytest
import resend

from app.core.config import settings
from app.email.contracts import EmailMessage, EmailType
from app.email.dependencies import build_email_provider
from app.email.errors import (
    EmailProviderAuthenticationError,
    EmailProviderConfigurationError,
    EmailProviderInvalidRequestError,
    EmailProviderRateLimitedError,
    EmailProviderUnavailableError,
)
from app.email.providers.dev import DevEmailProvider
from app.email.providers.resend import ResendEmailProvider
from app.email.service import send_password_reset_email

_FAKE_API_KEY = "".join(("re_", "abcdefghijklmnopqrstuvwx0123456789"))


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


def _message(**overrides: Any) -> EmailMessage:
    defaults: dict[str, Any] = dict(
        email_type=EmailType.PASSWORD_RESET,
        to_email="jane.doe@example.com",
        subject="Reset your Conversa password",
        html_body="<p>reset link</p>",
        text_body="reset link",
    )
    defaults.update(overrides)
    return EmailMessage(**defaults)


# --- DevEmailProvider: never makes an external call ------------------------


def test_dev_provider_never_calls_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}

    def _fail_if_called(*args: Any, **kwargs: Any) -> None:
        called["count"] += 1
        raise AssertionError("DevEmailProvider must never invoke the Resend SDK.")

    monkeypatch.setattr(resend.Emails, "send", _fail_if_called)
    provider = DevEmailProvider()
    result = provider.send(_message())
    assert called["count"] == 0
    assert result.success is True
    assert result.provider_key == "dev"


def test_dev_provider_makes_no_http_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def _fail_if_called(*args: Any, **kwargs: Any) -> httpx.Response:
        raise AssertionError("DevEmailProvider must never perform HTTP requests.")

    monkeypatch.setattr(httpx, "post", _fail_if_called)
    monkeypatch.setattr(httpx, "get", _fail_if_called)
    DevEmailProvider().send(_message())


# --- build_email_provider() selection policy --------------------------------


def test_build_email_provider_defaults_to_dev_in_development() -> None:
    with _settings_override(APP_ENV="development", TRANSACTIONAL_EMAIL_PROVIDER="dev"):
        provider = build_email_provider()
    assert provider.provider_key == "dev"


def test_build_email_provider_refuses_silent_dev_fallback_in_production() -> None:
    with _settings_override(APP_ENV="production", TRANSACTIONAL_EMAIL_PROVIDER="dev"):
        with pytest.raises(EmailProviderConfigurationError, match="Refusing to silently no-op"):
            build_email_provider()


@pytest.mark.parametrize("app_env", ["staging", "pilot", ""])
def test_build_email_provider_refuses_silent_dev_outside_dev_test(app_env: str) -> None:
    with _settings_override(APP_ENV=app_env, TRANSACTIONAL_EMAIL_PROVIDER="dev"):
        with pytest.raises(EmailProviderConfigurationError):
            build_email_provider()


def test_build_email_provider_resend_missing_api_key_fails_clearly() -> None:
    with _settings_override(APP_ENV="production", TRANSACTIONAL_EMAIL_PROVIDER="resend", RESEND_API_KEY="", EMAIL_FROM_ADDRESS="noreply@example.com"):
        with pytest.raises(EmailProviderConfigurationError, match="RESEND_API_KEY"):
            build_email_provider()


def test_build_email_provider_resend_missing_from_address_fails_clearly() -> None:
    with _settings_override(APP_ENV="production", TRANSACTIONAL_EMAIL_PROVIDER="resend", RESEND_API_KEY=_FAKE_API_KEY, EMAIL_FROM_ADDRESS=""):
        with pytest.raises(EmailProviderConfigurationError, match="EMAIL_FROM_ADDRESS"):
            build_email_provider()


def test_build_email_provider_unsupported_provider_fails_clearly() -> None:
    with _settings_override(APP_ENV="development", TRANSACTIONAL_EMAIL_PROVIDER="sendgrid"):
        with pytest.raises(EmailProviderConfigurationError, match="Unsupported TRANSACTIONAL_EMAIL_PROVIDER"):
            build_email_provider()


def test_build_email_provider_resend_configured_registers_real_provider() -> None:
    with _settings_override(
        APP_ENV="production", TRANSACTIONAL_EMAIL_PROVIDER="resend",
        RESEND_API_KEY=_FAKE_API_KEY, EMAIL_FROM_ADDRESS="noreply@example.com", EMAIL_FROM_NAME="Conversa",
    ):
        provider = build_email_provider()
    assert isinstance(provider, ResendEmailProvider)
    assert provider.provider_key == "resend"


# --- ResendEmailProvider construction validation ----------------------------


def test_resend_provider_missing_api_key_raises_configuration_error() -> None:
    with pytest.raises(EmailProviderConfigurationError, match="RESEND_API_KEY"):
        ResendEmailProvider(api_key="", from_address="noreply@example.com", from_name="Conversa")


def test_resend_provider_missing_from_address_raises_configuration_error() -> None:
    with pytest.raises(EmailProviderConfigurationError, match="EMAIL_FROM_ADDRESS"):
        ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="", from_name="Conversa")


# --- ResendEmailProvider send() ---------------------------------------------


def test_resend_provider_send_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_send(params: dict) -> dict:
        captured["params"] = params
        captured["api_key"] = resend.api_key
        return {"id": "email-abc123"}

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")
    result = provider.send(_message())

    assert result.success is True
    assert result.provider_key == "resend"
    assert result.provider_message_id == "email-abc123"
    assert captured["params"]["to"] == ["jane.doe@example.com"]
    assert captured["params"]["from"] == "Conversa <noreply@example.com>"
    assert captured["api_key"] == _FAKE_API_KEY


def test_resend_provider_raises_rate_limited_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        raise resend.exceptions.RateLimitError(message="too many requests", error_type="rate_limit_exceeded", code=429)

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")
    with pytest.raises(EmailProviderRateLimitedError):
        provider.send(_message())


def test_resend_provider_raises_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        raise resend.exceptions.InvalidApiKeyError(message="invalid key", error_type="authentication_error", code=401)

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")
    with pytest.raises(EmailProviderAuthenticationError):
        provider.send(_message())


def test_resend_provider_raises_invalid_request_error_on_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        raise resend.exceptions.ValidationError(message="invalid recipient", error_type="validation_error", code=400)

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")
    with pytest.raises(EmailProviderInvalidRequestError):
        provider.send(_message())


def test_resend_provider_raises_unavailable_error_on_application_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        raise resend.exceptions.ApplicationError(message="internal error", error_type="application_error", code=500)

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")
    with pytest.raises(EmailProviderUnavailableError):
        provider.send(_message())


def test_resend_provider_raises_unavailable_error_on_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        raise ConnectionError("could not reach resend.com")

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")
    with pytest.raises(EmailProviderUnavailableError):
        provider.send(_message())


def test_resend_provider_error_messages_never_contain_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        raise resend.exceptions.InvalidApiKeyError(message="invalid key", error_type="authentication_error", code=401)

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")
    with pytest.raises(EmailProviderAuthenticationError) as excinfo:
        provider.send(_message())
    assert _FAKE_API_KEY not in str(excinfo.value)


# --- observability -----------------------------------------------------------


@contextmanager
def _capture_logger(name: str) -> Iterator[list[logging.LogRecord]]:
    # A dedicated handler attached directly to this logger, rather than
    # relying on caplog's root-logger propagation/level capture - robust
    # against any other test module in this large suite mutating global
    # logging state (root level, handlers, etc.), matching the same
    # direct-handler pattern tests/test_widget_operations.py already uses.
    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(name)
    handler = _ListHandler()
    original_level = logger.level
    original_disabled = logger.disabled
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Other test modules in this suite exercise logging.config-based setup
    # (Azure Monitor OpenTelemetry logging integration) that can leave
    # pre-existing loggers process-globally disabled - restore this logger's
    # enabled state for the duration of the test regardless of that, since
    # it is unrelated to what this test is verifying.
    logger.disabled = False
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.disabled = original_disabled


def test_send_password_reset_email_logs_safe_observability_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        return {"id": "email-xyz"}

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")

    with _capture_logger("app.email.service") as records:
        result = send_password_reset_email(provider, to_email="jane.doe@example.com", reset_token="super-secret-reset-token-value")

    assert result is not None
    assert result.success is True

    [record] = records
    payload = json.loads(record.getMessage())
    assert payload["event"] == "email.send"
    assert payload["provider"] == "resend"
    assert payload["email_type"] == "password_reset"
    assert payload["success"] is True
    assert "latency_ms" in payload
    assert "retry_count" in payload
    # No raw email address, no token, no API key anywhere in the log line.
    assert "jane.doe@example.com" not in record.getMessage()
    assert "super-secret-reset-token-value" not in record.getMessage()
    assert _FAKE_API_KEY not in record.getMessage()


def test_send_password_reset_email_provider_failure_is_observed_and_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(params: dict) -> dict:
        raise resend.exceptions.ApplicationError(message="internal error", error_type="application_error", code=500)

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))
    provider = ResendEmailProvider(api_key=_FAKE_API_KEY, from_address="noreply@example.com", from_name="Conversa")

    with _capture_logger("app.email.service") as records:
        # Must not raise - a provider failure is fail-safe by design.
        result = send_password_reset_email(provider, to_email="jane.doe@example.com", reset_token="super-secret-reset-token-value")

    assert result is None
    [record] = records
    payload = json.loads(record.getMessage())
    assert payload["event"] == "email.send_failed"
    assert payload["success"] is False
    assert payload["error_code"] == "EMAIL_PROVIDER_UNAVAILABLE"
    assert "super-secret-reset-token-value" not in record.getMessage()
    assert _FAKE_API_KEY not in record.getMessage()
