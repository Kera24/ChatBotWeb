"""Tests for app.alerting.dispatcher: severity filtering, dedup/cooldown,
provider-failure handling (must never raise), and the AlertEvent ->
AlertNotification conversion that reuses app.observability.alerts.evaluate_alerts's
output rather than recomputing any threshold."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.alerting.contracts import AlertDeliveryResult, AlertNotification, AlertSeverity
from app.alerting.cooldown import AlertCooldownStore
from app.alerting.dispatcher import alert_event_to_notification, dispatch_alerts
from app.alerting.errors import AlertProviderUnavailableError
from app.alerting.providers.base import AlertProvider
from app.observability.alerts import AlertEvent


class _RecordingProvider(AlertProvider):
    provider_key = "recording"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[AlertNotification] = []
        self._fail = fail

    def deliver(self, notification: AlertNotification) -> AlertDeliveryResult:
        self.calls.append(notification)
        if self._fail:
            raise AlertProviderUnavailableError("simulated provider outage")
        return AlertDeliveryResult(provider_key=self.provider_key, success=True, latency_ms=1)


class _ExplodingProvider(AlertProvider):
    provider_key = "exploding"

    def deliver(self, notification: AlertNotification) -> AlertDeliveryResult:
        raise RuntimeError("not an AlertProviderError at all")


def _notification(**overrides) -> AlertNotification:
    defaults = dict(
        alert_key="p95_latency_high",
        category="p95_latency_high",
        severity=AlertSeverity.WARNING,
        message="p95 latency 9000ms exceeds threshold 8000ms",
        source_subsystem="ai_observability",
        triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        organisation_id="org-1",
        workspace_id="ws-1",
        assistant_id="asst-1",
    )
    defaults.update(overrides)
    return AlertNotification(**defaults)


# --- AlertEvent -> AlertNotification conversion -------------------------------


def test_alert_event_to_notification_reuses_evaluate_alerts_output() -> None:
    event = AlertEvent(
        alert_key="provider_error_rate_high",
        severity="critical",
        message="Provider error rate 15.0% exceeds threshold 10.0%",
        metric_value=15.0,
        threshold_value=10.0,
        triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    notification = alert_event_to_notification(
        event, source_subsystem="ai_observability", organisation_id="org-1", workspace_id="ws-1", assistant_id="asst-1",
    )
    assert notification.alert_key == "provider_error_rate_high"
    assert notification.severity == AlertSeverity.CRITICAL
    assert notification.metrics == {"metric_value": 15.0, "threshold_value": 10.0}
    assert notification.message == event.message


# --- severity filtering --------------------------------------------------------


def test_below_min_severity_is_skipped_without_calling_provider(tmp_path) -> None:
    provider = _RecordingProvider()
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    outcomes = dispatch_alerts(
        [_notification(severity=AlertSeverity.INFO)],
        provider=provider, cooldown_store=store, min_severity=AlertSeverity.WARNING, cooldown_seconds=0,
    )
    [outcome] = outcomes
    assert outcome.delivered is False
    assert outcome.reason == "below_min_severity"
    assert provider.calls == []


def test_at_or_above_min_severity_is_delivered(tmp_path) -> None:
    provider = _RecordingProvider()
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    outcomes = dispatch_alerts(
        [_notification(severity=AlertSeverity.CRITICAL)],
        provider=provider, cooldown_store=store, min_severity=AlertSeverity.WARNING, cooldown_seconds=0,
    )
    [outcome] = outcomes
    assert outcome.delivered is True
    assert len(provider.calls) == 1


# --- deduplication / cooldown --------------------------------------------------


def test_second_delivery_within_cooldown_window_is_skipped(tmp_path) -> None:
    provider = _RecordingProvider()
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    first = dispatch_alerts([_notification()], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=1800, now=now)
    second = dispatch_alerts(
        [_notification()], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=1800,
        now=now + timedelta(minutes=10),
    )

    assert first[0].delivered is True
    assert second[0].delivered is False
    assert second[0].reason == "cooldown_active"
    assert len(provider.calls) == 1


def test_delivery_after_cooldown_expires_is_allowed_again(tmp_path) -> None:
    provider = _RecordingProvider()
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    dispatch_alerts([_notification()], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=60, now=now)
    later = dispatch_alerts(
        [_notification()], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=60,
        now=now + timedelta(minutes=5),
    )

    assert later[0].delivered is True
    assert len(provider.calls) == 2


def test_different_dedup_scopes_do_not_share_a_cooldown(tmp_path) -> None:
    provider = _RecordingProvider()
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    dispatch_alerts([_notification(workspace_id="ws-1")], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=1800, now=now)
    outcomes = dispatch_alerts([_notification(workspace_id="ws-2")], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=1800, now=now)

    assert outcomes[0].delivered is True
    assert len(provider.calls) == 2


# --- provider failure handling: dispatcher must never raise -------------------


def test_classified_provider_failure_is_observed_and_swallowed(tmp_path) -> None:
    provider = _RecordingProvider(fail=True)
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    outcomes = dispatch_alerts([_notification()], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=0)
    [outcome] = outcomes
    assert outcome.delivered is False
    assert outcome.reason == "delivery_failed"


def test_unexpected_provider_exception_never_propagates(tmp_path) -> None:
    provider = _ExplodingProvider()
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    # Must not raise - a provider bug must never crash the caller.
    outcomes = dispatch_alerts([_notification()], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=0)
    [outcome] = outcomes
    assert outcome.delivered is False
    assert outcome.reason == "delivery_failed"


def test_failed_delivery_does_not_record_a_cooldown(tmp_path) -> None:
    provider = _RecordingProvider(fail=True)
    store = AlertCooldownStore(tmp_path / "cooldown.json")
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    dispatch_alerts([_notification()], provider=provider, cooldown_store=store, min_severity=AlertSeverity.INFO, cooldown_seconds=1800, now=now)
    assert store.last_delivered_at(_notification().dedup_key()) is None


# --- safe payload / redaction --------------------------------------------------


def test_notification_message_is_redacted_on_construction() -> None:
    notification = _notification(message="session token pss_live_abcdef123456.secretpart leaked in message")
    assert "pss_live_abcdef123456.secretpart" not in notification.message
    assert "[redacted" in notification.message


def test_notification_metrics_redact_sensitive_field_names() -> None:
    notification = _notification(metrics={"api_key": "sk-should-not-appear", "metric_value": 12.5})
    assert notification.metrics["api_key"] == "[redacted]"
    assert notification.metrics["metric_value"] == 12.5
