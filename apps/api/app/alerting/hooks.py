from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.alerting.contracts import AlertNotification, AlertSeverity, MetricValue
from app.alerting.cooldown import AlertCooldownStore
from app.alerting.dependencies import build_alert_provider
from app.alerting.dispatcher import dispatch_alerts
from app.core.config import settings
from app.operations.logging import log_operational_event

logger = logging.getLogger("app.alerting.hooks")


def notify_gate_failure(
    *,
    alert_key: str,
    category: str,
    message: str,
    source_subsystem: str,
    organisation_id: str,
    workspace_id: str,
    assistant_id: str | None = None,
    correlation_id: str | None = None,
    metrics: dict[str, MetricValue] | None = None,
) -> None:
    """Fail-safe alert dispatch for call sites where the alert condition is
    already computed by other, unrelated logic (an evaluation release gate,
    a regression report) rather than by app.observability.alerts -
    deliberately never raises, so a misconfigured alert provider or an
    unreachable webhook can never affect the CLI's own exit code or stdout
    contract (see app.operations.eval_release_gate_check /
    eval_regression_report, whose existing tests assert exact stdout).
    Mirrors the existing "wrap a new cross-cutting concern in try/except,
    default to no-op" pattern (see app.observability.ai_trace_recorder)."""
    try:
        notification = AlertNotification(
            alert_key=alert_key,
            category=category,
            severity=AlertSeverity.CRITICAL,
            message=message,
            source_subsystem=source_subsystem,
            triggered_at=datetime.now(timezone.utc),
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            assistant_id=assistant_id,
            correlation_id=correlation_id,
            metrics=metrics or {},
        )
        provider = build_alert_provider()
        cooldown_store = AlertCooldownStore(Path(settings.ALERT_COOLDOWN_STATE_PATH))
        dispatch_alerts(
            [notification],
            provider=provider,
            cooldown_store=cooldown_store,
            min_severity=AlertSeverity(settings.ALERT_MIN_SEVERITY),
            cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS,
        )
    except Exception:
        log_operational_event(
            logger,
            {"event": "alert.hook_failed", "alert_key": alert_key, "category": category},
            level=logging.ERROR,
        )
