from __future__ import annotations

import json
from pathlib import Path


REQUIRED_ALERT_FIELDS = {"alert_id", "severity", "signal", "threshold", "evaluation_window", "consecutive_failures", "runbook"}


def validate_alert_policy(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    alerts = data.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raise ValueError("Alert policy requires a non-empty alerts list.")
    seen: set[str] = set()
    for alert in alerts:
        missing = REQUIRED_ALERT_FIELDS.difference(alert)
        if missing:
            raise ValueError(f"Alert is missing fields: {sorted(missing)}")
        alert_id = str(alert["alert_id"])
        if alert_id in seen:
            raise ValueError(f"Duplicate alert_id: {alert_id}")
        seen.add(alert_id)
        if alert["severity"] not in {"warning", "incident", "critical"}:
            raise ValueError(f"Invalid severity for {alert_id}")
        forbidden = json.dumps(alert).lower()
        if "message body" in forbidden or "session_token" in forbidden or "answer body" in forbidden:
            raise ValueError(f"Sensitive alert signal for {alert_id}")
    return alerts

