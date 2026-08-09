from app.alerting.errors import AlertProviderConfigurationError
from app.alerting.providers.base import AlertProvider
from app.alerting.providers.dev import DevAlertProvider
from app.alerting.providers.email import EmailAlertProvider
from app.alerting.providers.slack import SlackWebhookAlertProvider
from app.core.config import settings
from app.email.dependencies import build_email_provider

# development/test: ALERT_PROVIDER left at its "dev" default is always safe
# - DevAlertProvider never makes an external call, so it satisfies "dev/test
# must not send external notifications unless explicitly enabled" (P1
# alert-delivery spec) without needing an APP_ENV check the way
# app.email.dependencies.build_email_provider needs one. Selecting a real
# provider ("email"/"slack") is exactly that explicit enablement, in any
# environment.


def build_alert_provider() -> AlertProvider:
    """Called from the alert-delivery CLI (app.operations.alert_dispatch_run)
    and from fail-safe alert hooks (app.alerting.hooks) - raises immediately
    on an explicitly-selected-but-misconfigured provider rather than
    silently falling back to a no-op, matching
    app.email.dependencies.build_email_provider's fail-fast policy."""
    provider_key = settings.ALERT_PROVIDER.strip().lower()
    if provider_key == "dev":
        return DevAlertProvider()
    if provider_key == "email":
        return _build_email_alert_provider()
    if provider_key == "slack":
        return _build_slack_alert_provider()
    raise AlertProviderConfigurationError(
        f"Unsupported ALERT_PROVIDER {settings.ALERT_PROVIDER!r}. Supported values: 'dev', 'email', 'slack'."
    )


def _build_email_alert_provider() -> EmailAlertProvider:
    recipients = _parse_recipients(settings.ALERT_EMAIL_TO)
    if not recipients:
        raise AlertProviderConfigurationError(
            "ALERT_PROVIDER=email requires ALERT_EMAIL_TO to be set (comma-separated addresses)."
        )
    return EmailAlertProvider(email_provider=build_email_provider(), recipients=recipients)


def _build_slack_alert_provider() -> SlackWebhookAlertProvider:
    if not settings.SLACK_WEBHOOK_URL:
        raise AlertProviderConfigurationError("ALERT_PROVIDER=slack requires SLACK_WEBHOOK_URL to be set.")
    return SlackWebhookAlertProvider(webhook_url=settings.SLACK_WEBHOOK_URL)


def _parse_recipients(raw: str) -> list[str]:
    return [entry.strip() for entry in raw.split(",") if entry.strip()]
