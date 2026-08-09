from html import escape
from time import perf_counter

from app.alerting.contracts import AlertDeliveryResult, AlertNotification
from app.alerting.errors import AlertProviderConfigurationError, AlertProviderUnavailableError
from app.alerting.providers.base import AlertProvider
from app.email.contracts import EmailMessage, EmailType
from app.email.errors import EmailProviderError
from app.email.providers.base import TransactionalEmailProvider


class EmailAlertProvider(AlertProvider):
    """Delivers alerts by reusing the existing transactional email provider
    abstraction (app.email.providers.base.TransactionalEmailProvider) -
    never calls Resend or any other vendor SDK directly. Sends one message
    per configured recipient; succeeds if at least one recipient accepted
    the message, since a partial failure across a distribution list is
    still a delivered alert."""

    provider_key = "email"

    def __init__(self, *, email_provider: TransactionalEmailProvider, recipients: list[str]) -> None:
        if not recipients:
            raise AlertProviderConfigurationError(
                "EmailAlertProvider requires at least one recipient. Set ALERT_EMAIL_TO."
            )
        self._email_provider = email_provider
        self._recipients = recipients

    def deliver(self, notification: AlertNotification) -> AlertDeliveryResult:
        subject, html_body, text_body = _render(notification)
        started_at = perf_counter()
        delivered_count = 0
        last_error: EmailProviderError | None = None
        for recipient in self._recipients:
            message = EmailMessage(
                email_type=EmailType.OPERATIONAL_ALERT,
                to_email=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
            try:
                self._email_provider.send(message)
                delivered_count += 1
            except EmailProviderError as exc:
                last_error = exc

        latency_ms = int((perf_counter() - started_at) * 1000)
        if delivered_count == 0 and last_error is not None:
            raise AlertProviderUnavailableError(
                f"EmailAlertProvider could not deliver to any of {len(self._recipients)} recipient(s): {last_error.code}"
            )
        return AlertDeliveryResult(provider_key=self.provider_key, success=True, latency_ms=latency_ms)


def _render(notification: AlertNotification) -> tuple[str, str, str]:
    subject = f"[Conversa Alert:{notification.severity.value.upper()}] {notification.category}"
    lines = [notification.message, "", f"Source subsystem: {notification.source_subsystem}"]
    if notification.organisation_id:
        lines.append(f"Organisation: {notification.organisation_id}")
    if notification.workspace_id:
        lines.append(f"Workspace: {notification.workspace_id}")
    if notification.assistant_id:
        lines.append(f"Assistant: {notification.assistant_id}")
    if notification.correlation_id:
        lines.append(f"Correlation ID: {notification.correlation_id}")
    if notification.metrics:
        lines.append("")
        lines.append("Metrics:")
        lines.extend(f"  {key}: {value}" for key, value in notification.metrics.items())
    lines.append("")
    lines.append(f"Triggered at: {notification.triggered_at.isoformat()}")

    text_body = "\n".join(lines)
    html_body = "<br>".join(escape(line) if line else "&nbsp;" for line in lines)
    return subject, html_body, text_body
