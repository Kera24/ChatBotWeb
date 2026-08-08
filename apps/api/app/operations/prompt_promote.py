"""CLI: run the evaluation-gated promotion check for one candidate
PromptVersion (spec section 9) - wraps app.evaluation.prompt_promotion_gate.

    python -m app.operations.prompt_promote --candidate-version <id> --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--format text|json]

This only runs and reports the gate - it never transitions the version's
status itself (approval is a deliberate, separate action taken through the
API/dashboard by an authorised reviewer, matching this codebase's existing
"no automatic-promotion path" rule for evaluation candidates).

Exits 0 if the gate passes, 1 if it does not (blocking), 2 on an operational
error (dataset/version not found, or the run's recorded prompt identity did
not match the requested candidate - see PromptGateIntegrityError).
"""

from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.evaluation.prompt_promotion_gate import PromptGateIntegrityError, evaluate_prompt_candidate
from app.repositories import evaluation_repository


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the evaluation-gated promotion check for one candidate prompt version.")
    parser.add_argument("--candidate-version", required=True, help="Candidate PromptVersion id.")
    parser.add_argument("--dataset", required=True, help="Evaluation dataset id.")
    parser.add_argument("--assistant", required=True, help="Assistant (widget) id.")
    parser.add_argument("--organisation", required=True, help="Organisation id.")
    parser.add_argument("--workspace", required=True, help="Workspace id.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    with SessionLocal() as db:
        dataset = evaluation_repository.get_dataset(db, organisation_id=args.organisation, workspace_id=args.workspace, dataset_id=args.dataset)
        if dataset is None:
            print(f"Evaluation dataset {args.dataset!r} not found for tenant workspace.", file=sys.stderr)
            return 2
        try:
            result = evaluate_prompt_candidate(
                db,
                organisation_id=args.organisation,
                workspace_id=args.workspace,
                widget_id=args.assistant,
                dataset=dataset,
                candidate_version_id=args.candidate_version,
                created_by="cli:prompt_promote",
            )
        except PromptGateIntegrityError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    payload = {**result.verdict.as_dict(), "candidate_run_id": result.candidate_run_id, "baseline_run_id": result.baseline_run_id}
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(f"Prompt promotion gate for candidate {args.candidate_version}: {'PASSED' if result.verdict.passed else 'FAILED'}")
        print(f"  candidate_run_id: {result.candidate_run_id}")
        print(f"  baseline_run_id: {result.baseline_run_id}")
        for reason in result.verdict.reasons:
            print(f"  - {reason}")

    return 0 if result.verdict.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
