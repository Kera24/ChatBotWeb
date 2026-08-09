"""Tests for the proactive alert-delivery layer (P1 launch-hardening item):
AlertProvider abstraction, DevAlertProvider, EmailAlertProvider,
SlackWebhookAlertProvider, and app.alerting.dependencies.build_alert_provider's
selection/misconfiguration policy. Deterministic, no network required -
EmailAlertProvider is exercised against a fake TransactionalEmailProvider and
SlackWebhookAlertProvider's HTTP call is intercepted via httpx.MockTransport."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx
import pytest

from app.alerting.contracts import AlertDeliveryResult, AlertNotification, AlertSeverity
from app.alerting.dependencies import build_alert_provider
from app.alerting.errors import (
    AlertProviderConfigurationError,
    AlertProviderInvalidRequestError,
    AlertProviderUnavailableError,
)
from app.alerting.providers.dev import DevAlertProvider
from app.alerting.providers.email import EmailAlertProvider
from app.alerting.providers.slack import SlackWebhookAlertProvider
from app.core.config import settings
from app.email.contracts import EmailMessage, EmailType
from app.email.errors import EmailProviderUnavailableError
from app.email.providers.base import TransactionalEmailProvider


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


def _notification(**overrides: Any) -> AlertNotification:
    defaults: dict[str, Any] = dict(
        alert_key="provider_error_rate_high",
        category="provider_error_rate_high",
        severity=AlertSeverity.CRITICAL,
        message="Provider error rate 15.0% exceeds threshold 10.0%",
        source_subsystem="ai_observability",
        triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        organisation_id="org-1",
        workspace_id="ws-1",
        assistant_id="asst-1",
        correlation_id="trace-abc",
        metrics={"metric_value": 15.0, "threshold_value": 10.0},
    )
    defaults.update(overrides)
    return AlertNotification(**defaults)


class _FakeEmailProvider(TransactionalEmailProvider):
    provider_key = "fake"

    def __init__(self, *, fail_for: set[str] | None = None) -> None:
        self.sent: list[EmailMessage] = []
        self._fail_for = fail_for or set()

    def send(self, message: EmailMessage) -> Any:
        if message.to_email in self._fail_for:
            raise EmailProviderUnavailableError("simulated failure")
        self.sent.append(message)
        return None  # EmailAlertProvider.deliver() discards the return value


# --- DevAlertProvider: never makes an external call -------------------------


def test_dev_provider_never_makes_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_if_called(*args: Any, **kwargs: Any) -> httpx.Response:
        raise AssertionError("DevAlertProvider must never perform HTTP requests.")

    monkeypatch.setattr(httpx, "post", _fail_if_called)
    monkeypatch.setattr(httpx, "get", _fail_if_called)

    provider = DevAlertProvider()
    result = provider.deliver(_notification())
    assert result.success is True
    assert result.provider_key == "dev"


def test_dev_provider_logs_only_safe_fields() -> None:
    import json
    import logging

    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("app.alerting.providers.dev")
    handler = _ListHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        DevAlertProvider().deliver(_notification(message="Provider error rate 15.0% exceeds threshold 10.0%"))
    finally:
        logger.removeHandler(handler)

    [record] = records
    payload = json.loads(record.getMessage())
    assert payload["event"] == "alert.dev_provider.simulated_delivery"
    assert payload["alert_key"] == "provider_error_rate_high"
    assert payload["severity"] == "critical"
    assert "message" not in payload


# --- EmailAlertProvider -------------------------------------------------------


def test_email_alert_provider_requires_recipients() -> None:
    with pytest.raises(AlertProviderConfigurationError, match="ALERT_EMAIL_TO"):
        EmailAlertProvider(email_provider=_FakeEmailProvider(), recipients=[])


def test_email_alert_provider_sends_via_transactional_email_abstraction() -> None:
    fake = _FakeEmailProvider()
    provider = EmailAlertProvider(email_provider=fake, recipients=["ops@example.com"])

    result = provider.deliver(_notification())

    assert result.success is True
    assert result.provider_key == "email"
    [message] = fake.sent
    assert message.to_email == "ops@example.com"
    assert message.email_type == EmailType.OPERATIONAL_ALERT
    assert "provider_error_rate_high" in message.subject
    assert "Provider error rate" in message.text_body


def test_email_alert_provider_succeeds_if_any_recipient_accepts() -> None:
    fake = _FakeEmailProvider(fail_for={"broken@example.com"})
    provider = EmailAlertProvider(email_provider=fake, recipients=["broken@example.com", "ops@example.com"])

    result = provider.deliver(_notification())

    assert result.success is True
    assert len(fake.sent) == 1


def test_email_alert_provider_raises_when_all_recipients_fail() -> None:
    fake = _FakeEmailProvider(fail_for={"a@example.com", "b@example.com"})
    provider = EmailAlertProvider(email_provider=fake, recipients=["a@example.com", "b@example.com"])

    with pytest.raises(AlertProviderUnavailableError):
        provider.deliver(_notification())


# --- SlackWebhookAlertProvider ------------------------------------------------


def _slack_provider(handler, **overrides: Any) -> SlackWebhookAlertProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    defaults: dict[str, Any] = dict(webhook_url="https://hooks.slack.com/services/T0/B0/fake-secret", client=client)
    defaults.update(overrides)
    return SlackWebhookAlertProvider(**defaults)


def test_slack_provider_requires_webhook_url() -> None:
    with pytest.raises(AlertProviderConfigurationError, match="SLACK_WEBHOOK_URL"):
        SlackWebhookAlertProvider(webhook_url="")


def test_slack_provider_posts_safe_payload() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode("utf-8")
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True})

    provider = _slack_provider(handler)
    result = provider.deliver(_notification())

    assert result.success is True
    assert "provider_error_rate_high" in captured["body"]
    assert "org-1" in captured["body"]
    assert "trace-abc" in captured["body"]


def test_slack_provider_never_includes_webhook_url_in_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    provider = _slack_provider(handler, webhook_url="https://hooks.slack.com/services/T0/B0/super-secret-token")
    with pytest.raises(AlertProviderUnavailableError) as excinfo:
        provider.deliver(_notification())
    assert "super-secret-token" not in str(excinfo.value)


def test_slack_provider_raises_invalid_request_on_400() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="invalid_payload")

    provider = _slack_provider(handler)
    with pytest.raises(AlertProviderInvalidRequestError):
        provider.deliver(_notification())


def test_slack_provider_raises_configuration_error_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="no_service")

    provider = _slack_provider(handler)
    with pytest.raises(AlertProviderConfigurationError):
        provider.deliver(_notification())


def test_slack_provider_raises_unavailable_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    provider = _slack_provider(handler)
    with pytest.raises(AlertProviderUnavailableError):
        provider.deliver(_notification())


# --- build_alert_provider() selection policy ----------------------------------


def test_build_alert_provider_defaults_to_dev() -> None:
    with _settings_override(ALERT_PROVIDER="dev"):
        provider = build_alert_provider()
    assert isinstance(provider, DevAlertProvider)


def test_build_alert_provider_unsupported_provider_fails_clearly() -> None:
    with _settings_override(ALERT_PROVIDER="pagerduty"):
        with pytest.raises(AlertProviderConfigurationError, match="Unsupported ALERT_PROVIDER"):
            build_alert_provider()


def test_build_alert_provider_email_missing_recipients_fails_clearly() -> None:
    with _settings_override(ALERT_PROVIDER="email", ALERT_EMAIL_TO=""):
        with pytest.raises(AlertProviderConfigurationError, match="ALERT_EMAIL_TO"):
            build_alert_provider()


def test_build_alert_provider_slack_missing_webhook_fails_clearly() -> None:
    with _settings_override(ALERT_PROVIDER="slack", SLACK_WEBHOOK_URL=""):
        with pytest.raises(AlertProviderConfigurationError, match="SLACK_WEBHOOK_URL"):
            build_alert_provider()


def test_build_alert_provider_slack_configured_registers_real_provider() -> None:
    with _settings_override(ALERT_PROVIDER="slack", SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T0/B0/x"):
        provider = build_alert_provider()
    assert isinstance(provider, SlackWebhookAlertProvider)
    assert provider.provider_key == "slack"


def test_build_alert_provider_email_reuses_transactional_email_dependency() -> None:
    with _settings_override(
        ALERT_PROVIDER="email", ALERT_EMAIL_TO="ops@example.com",
        TRANSACTIONAL_EMAIL_PROVIDER="dev", APP_ENV="test",
    ):
        provider = build_alert_provider()
    assert isinstance(provider, EmailAlertProvider)
    assert provider.provider_key == "email"


# --- no secret leakage --------------------------------------------------------


def test_notification_never_serialises_a_slack_webhook_secret() -> None:
    notification = _notification(message="Provider error rate 15.0% exceeds threshold 10.0%")
    dumped = notification.model_dump_json()
    assert "hooks.slack.com" not in dumped
    assert "T0/B0" not in dumped
