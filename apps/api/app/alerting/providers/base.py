from abc import ABC, abstractmethod

from app.alerting.contracts import AlertDeliveryResult, AlertNotification


class AlertProvider(ABC):
    provider_key: str

    @abstractmethod
    def deliver(self, notification: AlertNotification) -> AlertDeliveryResult:
        """Deliver one alert. Must raise a classified
        app.alerting.errors.AlertProviderError (never a raw exception) on
        failure rather than silently returning success=False - matches the
        same "no silent fallback" contract TransactionalEmailProvider.send
        and AIProvider.generate already establish elsewhere in this
        codebase. Callers (see app.alerting.dispatcher) are responsible for
        catching that error so a provider failure can never crash the
        caller."""
