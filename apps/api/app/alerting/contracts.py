from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.observability.redaction import redact_free_text
from app.operations.logging import redact as redact_operational_metadata

MetricValue = float | int | str | None


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


_SEVERITY_RANK: dict[AlertSeverity, int] = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.CRITICAL: 2,
}


def severity_at_least(severity: AlertSeverity, *, minimum: AlertSeverity) -> bool:
    return _SEVERITY_RANK[severity] >= _SEVERITY_RANK[minimum]


class AlertNotification(BaseModel):
    """Safe-by-construction alert payload. Every field is one of the
    explicitly allowed metadata categories from the P1 alert-delivery spec:
    alert type, severity, source subsystem, timestamp, tenant/correlation
    ids, and safe aggregate metrics. Never add a free-text field that could
    carry prompt/document/conversation content or a raw customer identifier.

    `message`/`metrics` are redacted on construction (see the validators
    below) as a defense-in-depth backstop reusing the same redaction paths
    already trusted elsewhere in this codebase (app.observability.redaction
    for AI trace content, app.operations.logging for structured log
    events) - this does not replace callers being careful about what they
    put in a notification, it catches what they miss."""

    model_config = ConfigDict(frozen=True)

    alert_key: str
    category: str
    severity: AlertSeverity
    message: str
    source_subsystem: str
    triggered_at: datetime
    organisation_id: str | None = None
    workspace_id: str | None = None
    assistant_id: str | None = None
    correlation_id: str | None = None
    metrics: dict[str, MetricValue] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        return redact_free_text(value).text

    @field_validator("metrics")
    @classmethod
    def _redact_metrics(cls, value: dict[str, MetricValue]) -> dict[str, MetricValue]:
        return redact_operational_metadata(dict(value))

    def dedup_key(self) -> str:
        return "|".join(
            [self.organisation_id or "-", self.workspace_id or "-", self.assistant_id or "-", self.alert_key]
        )


class AlertDeliveryResult(BaseModel):
    provider_key: str
    success: bool
    latency_ms: int
