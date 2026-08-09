from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.alerting.contracts import AlertDeliveryResult, AlertNotification, AlertSeverity, MetricValue, severity_at_least
from app.alerting.cooldown import AlertCooldownStore
from app.alerting.errors import AlertProviderError
from app.alerting.providers.base import AlertProvider
from app.observability.alerts import AlertEvent
from app.operations.logging import log_operational_event

logger = logging.getLogger("app.alerting.dispatcher")


@dataclass(frozen=True)
class AlertDispatchOutcome:
    notification: AlertNotification
    delivered: bool
    reason: str  # "delivered" | "below_min_severity" | "cooldown_active" | "delivery_failed"
    result: AlertDeliveryResult | None = None


def alert_event_to_notification(
    event: AlertEvent,
    *,
    source_subsystem: str,
    organisation_id: str | None = None,
    workspace_id: str | None = None,
    assistant_id: str | None = None,
    correlation_id: str | None = None,
) -> AlertNotification:
    """Converts an already-evaluated app.observability.alerts.AlertEvent
    into a deliverable AlertNotification - deliberately does not
    re-evaluate any threshold; evaluate_alerts remains the single source of
    truth for alert conditions."""
    metrics: dict[str, MetricValue] = {}
    if event.metric_value is not None:
        metrics["metric_value"] = event.metric_value
    if event.threshold_value is not None:
        metrics["threshold_value"] = event.threshold_value
    return AlertNotification(
        alert_key=event.alert_key,
        category=event.alert_key,
        severity=AlertSeverity(event.severity),
        message=event.message,
        source_subsystem=source_subsystem,
        triggered_at=event.triggered_at,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        assistant_id=assistant_id,
        correlation_id=correlation_id,
        metrics=metrics,
    )


def dispatch_alerts(
    notifications: list[AlertNotification],
    *,
    provider: AlertProvider,
    cooldown_store: AlertCooldownStore,
    min_severity: AlertSeverity,
    cooldown_seconds: int,
    now: datetime | None = None,
) -> list[AlertDispatchOutcome]:
    now = now or datetime.now(timezone.utc)
    return [
        _dispatch_one(
            notification,
            provider=provider,
            cooldown_store=cooldown_store,
            min_severity=min_severity,
            cooldown_seconds=cooldown_seconds,
            now=now,
        )
        for notification in notifications
    ]


def _dispatch_one(
    notification: AlertNotification,
    *,
    provider: AlertProvider,
    cooldown_store: AlertCooldownStore,
    min_severity: AlertSeverity,
    cooldown_seconds: int,
    now: datetime,
) -> AlertDispatchOutcome:
    if not severity_at_least(notification.severity, minimum=min_severity):
        return AlertDispatchOutcome(notification=notification, delivered=False, reason="below_min_severity")

    dedup_key = notification.dedup_key()
    if cooldown_store.is_in_cooldown(dedup_key, cooldown_seconds=cooldown_seconds, now=now):
        return AlertDispatchOutcome(notification=notification, delivered=False, reason="cooldown_active")

    try:
        result = provider.deliver(notification)
    except AlertProviderError as exc:
        _log_failure(provider.provider_key, notification, error_code=exc.code)
        return AlertDispatchOutcome(notification=notification, delivered=False, reason="delivery_failed")
    except Exception:
        # Belt-and-braces: a provider must never be able to crash the caller
        # (CLI today, potentially an in-process call site later) even if it
        # raises something outside its own AlertProviderError family - see
        # requirement "provider delivery failure must never crash the API".
        _log_failure(provider.provider_key, notification, error_code="UNEXPECTED_PROVIDER_ERROR")
        return AlertDispatchOutcome(notification=notification, delivered=False, reason="delivery_failed")

    cooldown_store.record_delivery(dedup_key, now=now)
    log_operational_event(
        logger,
        {
            "event": "alert.delivered",
            "provider": result.provider_key,
            "alert_key": notification.alert_key,
            "category": notification.category,
            "severity": notification.severity.value,
            "latency_ms": result.latency_ms,
        },
    )
    return AlertDispatchOutcome(notification=notification, delivered=True, reason="delivered", result=result)


def _log_failure(provider_key: str, notification: AlertNotification, *, error_code: str) -> None:
    log_operational_event(
        logger,
        {
            "event": "alert.delivery_failed",
            "provider": provider_key,
            "alert_key": notification.alert_key,
            "category": notification.category,
            "severity": notification.severity.value,
            "error_code": error_code,
        },
        level=logging.ERROR,
    )
