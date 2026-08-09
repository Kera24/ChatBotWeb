from time import perf_counter

import httpx

from app.alerting.contracts import AlertDeliveryResult, AlertNotification
from app.alerting.errors import AlertProviderConfigurationError, AlertProviderInvalidRequestError, AlertProviderUnavailableError
from app.alerting.providers.base import AlertProvider

_SEVERITY_EMOJI = {"info": ":information_source:", "warning": ":warning:", "critical": ":rotating_light:"}
_BODY_EXCERPT_CHARS = 500


class SlackWebhookAlertProvider(AlertProvider):
    """Minimal Slack incoming-webhook client - posts a single safe text
    payload, no Slack SDK dependency. The webhook URL is itself a bearer
    credential (anyone holding it can post to the channel) and is treated
    the same way OpenRouterAIProvider treats its API key: never attached to
    any exception message, log line, or returned result."""

    provider_key = "slack"

    def __init__(self, *, webhook_url: str, timeout_seconds: float = 10.0, client: httpx.Client | None = None) -> None:
        if not webhook_url:
            raise AlertProviderConfigurationError(
                "SlackWebhookAlertProvider requires a non-empty webhook_url. Set SLACK_WEBHOOK_URL."
            )
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        # Optional injected client is test-only (mirrors
        # OpenRouterAIProvider's constructor, see tests/test_openrouter_provider.py).
        self._client = client

    def deliver(self, notification: AlertNotification) -> AlertDeliveryResult:
        payload = _build_payload(notification)
        started_at = perf_counter()
        try:
            response = self._send(payload)
        except httpx.TimeoutException as exc:
            raise AlertProviderUnavailableError(f"Slack webhook timed out after {self._timeout_seconds}s.") from exc
        except httpx.HTTPError as exc:
            raise AlertProviderUnavailableError("Could not reach the configured Slack webhook.") from exc
        latency_ms = int((perf_counter() - started_at) * 1000)

        self._raise_for_status(response)
        return AlertDeliveryResult(provider_key=self.provider_key, success=True, latency_ms=latency_ms)

    def _send(self, payload: dict) -> httpx.Response:
        if self._client is not None:
            return self._client.post(self._webhook_url, json=payload, timeout=self._timeout_seconds)
        return httpx.post(self._webhook_url, json=payload, timeout=self._timeout_seconds)

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 200:
            return
        if response.status_code == 404:
            raise AlertProviderConfigurationError("Slack rejected the webhook URL (HTTP 404) - it may have been revoked.")
        if response.status_code in (400, 403):
            raise AlertProviderInvalidRequestError(f"Slack rejected the alert payload (HTTP {response.status_code}).")
        raise AlertProviderUnavailableError(
            f"Slack webhook returned unexpected HTTP {response.status_code}: {response.text[:_BODY_EXCERPT_CHARS]}"
        )


def _build_payload(notification: AlertNotification) -> dict:
    emoji = _SEVERITY_EMOJI.get(notification.severity.value, "")
    lines = [
        f"{emoji} *[{notification.severity.value.upper()}] {notification.category}*".strip(),
        notification.message,
        f"subsystem: {notification.source_subsystem}",
    ]
    if notification.organisation_id:
        lines.append(f"organisation: {notification.organisation_id}")
    if notification.workspace_id:
        lines.append(f"workspace: {notification.workspace_id}")
    if notification.assistant_id:
        lines.append(f"assistant: {notification.assistant_id}")
    if notification.correlation_id:
        lines.append(f"correlation_id: {notification.correlation_id}")
    if notification.metrics:
        metrics_text = ", ".join(f"{key}={value}" for key, value in notification.metrics.items())
        lines.append(f"metrics: {metrics_text}")
    lines.append(f"triggered_at: {notification.triggered_at.isoformat()}")
    return {"text": "\n".join(lines)}
