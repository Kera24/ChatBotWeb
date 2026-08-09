"""CLI: evaluate AI observability alert thresholds and proactively deliver
any triggered alerts through the configured AlertProvider
(app.alerting.dependencies.build_alert_provider).

    python -m app.operations.alert_dispatch_run --organisation <id> --workspace <id> [--assistant <id>] [--window-hours <float>] [--dry-run]

Reuses app.observability.alerts.evaluate_alerts for threshold evaluation -
this CLI adds delivery (severity filtering, dedup/cooldown, provider
dispatch) on top of it, it never recomputes an alert condition itself.
Intended to run on a schedule (cron/systemd timer, same pattern as
observability_retention_cleanup.py / production_signal_scan.py).

`--dry-run` evaluates and reports what would be delivered without calling
the configured provider or touching the cooldown store.

Exits 0 on success (including "nothing triggered"), 2 on an operational
error (unknown workspace, misconfigured provider).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.alerting.contracts import AlertSeverity
from app.alerting.cooldown import AlertCooldownStore
from app.alerting.dependencies import build_alert_provider
from app.alerting.dispatcher import alert_event_to_notification, dispatch_alerts
from app.alerting.errors import AlertProviderConfigurationError
from app.core.config import settings
from app.db.session import SessionLocal
from app.observability.alerts import evaluate_alerts
from app.repositories.workspace_repository import get_workspace_for_organisation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate AI observability alert thresholds and deliver any triggered alerts.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--assistant", default=None, help="Restrict evaluation to one assistant (widget) id.")
    parser.add_argument("--window-hours", type=float, default=1.0, help="Trailing evaluation window in hours (default 1.0).")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate and report what would be delivered without calling the configured provider.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.window_hours <= 0:
        print(f"Refusing to run with window-hours={args.window_hours} (must be positive).", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        workspace = get_workspace_for_organisation(db, organisation_id=args.organisation, workspace_id=args.workspace)
        if workspace is None:
            print(f"Workspace {args.workspace} not found for organisation {args.organisation}.", file=sys.stderr)
            return 2

        events = evaluate_alerts(
            db,
            organisation_id=args.organisation,
            workspace_id=args.workspace,
            assistant_id=args.assistant,
            window_hours=args.window_hours,
        )

    if not events:
        print(f"No alerts triggered in the trailing {args.window_hours}h window.")
        return 0

    notifications = [
        alert_event_to_notification(
            event,
            source_subsystem="ai_observability",
            organisation_id=args.organisation,
            workspace_id=args.workspace,
            assistant_id=args.assistant,
        )
        for event in events
    ]

    if args.dry_run:
        for notification in notifications:
            print(f"[dry-run] {notification.alert_key} (severity={notification.severity.value}): {notification.message}")
        return 0

    try:
        provider = build_alert_provider()
    except AlertProviderConfigurationError as exc:
        print(f"Alert provider misconfigured: {exc.message}", file=sys.stderr)
        return 2

    cooldown_store = AlertCooldownStore(Path(settings.ALERT_COOLDOWN_STATE_PATH))
    outcomes = dispatch_alerts(
        notifications,
        provider=provider,
        cooldown_store=cooldown_store,
        min_severity=AlertSeverity(settings.ALERT_MIN_SEVERITY),
        cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS,
        now=datetime.now(timezone.utc),
    )

    delivered = sum(1 for outcome in outcomes if outcome.delivered)
    skipped_severity = sum(1 for outcome in outcomes if outcome.reason == "below_min_severity")
    skipped_cooldown = sum(1 for outcome in outcomes if outcome.reason == "cooldown_active")
    failed = sum(1 for outcome in outcomes if outcome.reason == "delivery_failed")
    print(
        f"Evaluated {len(events)} alert(s): delivered {delivered}, skipped {skipped_severity} (below min severity), "
        f"skipped {skipped_cooldown} (cooldown), failed {failed}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
