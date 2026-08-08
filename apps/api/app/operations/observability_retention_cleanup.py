"""CLI: delete AI observability trace rows older than the configured
retention window.

    python -m app.operations.observability_retention_cleanup [--retention-days <int>] [--dry-run]

Intended to run on a schedule (cron/systemd timer, alongside the existing
`deployment/monitoring/check.sh` health-check pattern) against the production
database. `--retention-days` overrides `AI_TRACE_RETENTION_DAYS` for a
one-off run without touching the environment. `--dry-run` reports how many
trace rows would be deleted without deleting anything.

Exits 0 on success (including "nothing to delete"), 2 on an operational
error.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.db.models.ai_trace import AITrace
from app.db.session import SessionLocal
from app.observability.retention import cleanup_expired_traces


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete AI observability trace rows past the retention window.")
    parser.add_argument("--retention-days", type=int, default=None, help="Override AI_TRACE_RETENTION_DAYS for this run.")
    parser.add_argument("--dry-run", action="store_true", help="Report how many traces would be deleted without deleting them.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    retention_days = args.retention_days if args.retention_days is not None else settings.AI_TRACE_RETENTION_DAYS
    if retention_days <= 0:
        print(f"Refusing to run with retention_days={retention_days} (must be positive).", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        if args.dry_run:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            count = db.execute(select(func.count(AITrace.id)).where(AITrace.created_at < cutoff)).scalar_one()
            print(f"[dry-run] {count} trace(s) older than {cutoff.isoformat()} (retention_days={retention_days}) would be deleted.")
            return 0

        result = cleanup_expired_traces(db, retention_days=retention_days)
        print(
            f"Deleted {result.traces_deleted} trace(s) older than {result.cutoff.isoformat()} "
            f"(retention_days={retention_days}): {result.stages_deleted} stage rows, "
            f"{result.retrieval_deleted} retrieval rows, {result.model_calls_deleted} model-call rows, "
            f"{result.guardrails_deleted} guardrail rows."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
