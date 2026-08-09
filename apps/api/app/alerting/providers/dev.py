import logging
from time import perf_counter

from app.alerting.contracts import AlertDeliveryResult, AlertNotification
from app.alerting.providers.base import AlertProvider
from app.operations.logging import log_operational_event

logger = logging.getLogger("app.alerting.providers.dev")


class DevAlertProvider(AlertProvider):
    """Never makes a network call and never sends a real notification -
    this is the development/test default (see
    app.alerting.dependencies.build_alert_provider). Logs that a delivery
    would have happened, using only safe fields (alert key, category,
    severity, source subsystem), so the alert-delivery path stays
    observable locally without any risk of an accidental external send."""

    provider_key = "dev"

    def deliver(self, notification: AlertNotification) -> AlertDeliveryResult:
        started_at = perf_counter()
        log_operational_event(
            logger,
            {
                "event": "alert.dev_provider.simulated_delivery",
                "provider": self.provider_key,
                "alert_key": notification.alert_key,
                "category": notification.category,
                "severity": notification.severity.value,
                "source_subsystem": notification.source_subsystem,
                "organisation_id": notification.organisation_id,
                "workspace_id": notification.workspace_id,
            },
        )
        return AlertDeliveryResult(
            provider_key=self.provider_key,
            success=True,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )
