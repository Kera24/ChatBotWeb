"""CLI: check whether the production feedback loop's state allows a release
to proceed (spec section 9) - wraps app.evaluation.production_gate.

    python -m app.operations.eval_release_gate_check --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--format text|json] [--max-baseline-age-days <int>]

Intended to be one more step in scripts/release-gate.mjs, alongside the
existing eval:test/eval:launch steps. Graders remain advisory - this only
ever blocks on the deterministic conditions documented in
app.evaluation.production_gate.evaluate_production_readiness.

Exits 0 if the gate passes, 1 if it does not (blocking - matches
scripts/release-gate.mjs's convention of a non-zero exit from `npm run
<script>` failing that gate), 2 on an operational error (dataset not found).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.alerting.hooks import notify_gate_failure
from app.db.session import SessionLocal
from app.evaluation.production_gate import DEFAULT_MAX_BASELINE_AGE_DAYS, evaluate_production_readiness
from app.observability import otel_metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the production feedback loop's release gate for one assistant's dataset.")
    parser.add_argument("--dataset", required=True, help="Evaluation dataset id.")
    parser.add_argument("--assistant", required=True, help="Assistant (widget) id.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--max-baseline-age-days", type=int, default=DEFAULT_MAX_BASELINE_AGE_DAYS, help="Maximum age of the latest completed run before it counts as stale.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    with SessionLocal() as db:
        verdict = evaluate_production_readiness(
            db,
            organisation_id=args.organisation,
            workspace_id=args.workspace,
            widget_id=args.assistant,
            dataset_id=args.dataset,
            max_baseline_age_days=args.max_baseline_age_days,
        )

    otel_metrics.record_evaluation_gate_outcome(gate="release_gate", passed=verdict.passed)

    if not verdict.passed:
        notify_gate_failure(
            alert_key="evaluation_release_gate_failed",
            category="evaluation_gate_failure",
            message=f"Production release gate failed for dataset {args.dataset}: {'; '.join(verdict.reasons) or 'no reasons reported'}",
            source_subsystem="evaluation_release_gate",
            organisation_id=args.organisation,
            workspace_id=args.workspace,
            assistant_id=args.assistant,
            correlation_id=args.dataset,
        )

    if args.format == "json":
        print(json.dumps(verdict.as_dict(), indent=2))
    else:
        print(f"Production feedback loop release gate: {'PASSED' if verdict.passed else 'FAILED'}")
        for reason in verdict.reasons:
            print(f"  - {reason}")

    return 0 if verdict.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
