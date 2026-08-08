"""CLI: scan one assistant's recent production traffic for failure signals
and turn them into (or bump the occurrence count of) EvaluationCandidate
triage-queue rows.

    python -m app.operations.production_signal_scan --organisation <id> --workspace <id> --assistant <id> [--since-hours <int>] [--dry-run]

Matches app.operations.eval_run's --organisation/--workspace/--assistant
flag naming. Intended to run nightly on a schedule (cron/systemd timer, same
pattern as observability_retention_cleanup.py) - see
docs/06_Operations/Nightly_Evaluation_VPS_Guide.md. Requires an explicit
assistant scope per invocation, same as every other eval CLI in this
codebase; a multi-assistant nightly job loops this command once per assistant
id rather than this CLI enumerating tenants itself.

`--dry-run` reports how many signals would create vs. bump a candidate
without writing anything - it runs the same detection queries and dedup-hash
matching as a real scan, it just never calls the write path (see
app.evaluation.feedback.detector.scan_for_candidates's dry_run flag).

Exits 0 on success (including "no signals found"), 2 on an operational error.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.evaluation.feedback.detector import scan_for_candidates
from app.evaluation.policy import load_policy_from_env
from app.repositories.workspace_repository import get_workspace_for_organisation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan one assistant's recent production traffic for failure signals.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--assistant", required=True, help="Assistant (widget) id to scan.")
    parser.add_argument("--since-hours", type=int, default=24, help="Look back this many hours (default 24, i.e. a nightly window).")
    parser.add_argument("--dry-run", action="store_true", help="Run detection but roll back instead of committing any new/bumped candidates.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.since_hours <= 0:
        print(f"Refusing to run with since-hours={args.since_hours} (must be positive).", file=sys.stderr)
        return 2

    since = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)

    with SessionLocal() as db:
        workspace = get_workspace_for_organisation(db, organisation_id=args.organisation, workspace_id=args.workspace)
        if workspace is None:
            print(f"Workspace {args.workspace} not found for organisation {args.organisation}.", file=sys.stderr)
            return 2

        summary = scan_for_candidates(
            db,
            organisation_id=args.organisation,
            workspace_id=args.workspace,
            widget_id=args.assistant,
            since=since,
            policy=load_policy_from_env(),
            dry_run=args.dry_run,
        )

        if args.dry_run:
            print(
                f"[dry-run] scanned {summary.scanned_signals} signal(s) since {since.isoformat()}: "
                f"would create {summary.candidates_created}, bump {summary.candidates_bumped}."
            )
            return 0

        print(
            f"Scanned {summary.scanned_signals} signal(s) since {since.isoformat()}: "
            f"created {summary.candidates_created} new candidate(s), bumped {summary.candidates_bumped} existing candidate(s)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
