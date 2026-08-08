"""Evaluation-gated promotion for a candidate PromptVersion (spec section 9) -
mirrors app.evaluation.production_gate's shape: a deployment-agnostic
function that runs the real evaluation engine against one candidate version
and returns a plain verdict object. Never touches app.evaluation.policy or
app.evaluation.gate - only calls the unmodified evaluate_gate().

"Run the guardrail suite" (task spec section 6) is satisfied by this same
evaluation run: all 8 guardrail layers (A-H) execute unconditionally inside
RAGOrchestrator.answer() for every case, so a guardrail regression surfaces as
a scoring/hard-failure difference in the run this module already produces -
there is no separate parallel guardrail-only test runner.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import EvaluationDataset, EvaluationRun
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.gate import GateVerdict, evaluate_gate
from app.evaluation.policy import DEFAULT_POLICY
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository


class PromptGateIntegrityError(Exception):
    """Raised when the evaluation run's recorded prompt identity does not
    match the requested candidate - see docs/architecture/prompts.md's
    fail-loud design decision. A silent mismatch here would let the gate
    report PASS for a run that never actually exercised the candidate."""


@dataclass(frozen=True)
class PromptGateResult:
    verdict: GateVerdict
    candidate_run_id: str
    baseline_run_id: str | None


def _latest_baseline_run(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str, dataset_id: str) -> EvaluationRun | None:
    """The most recent completed run for this widget+dataset that was NOT
    itself a prompt-candidate gate run (prompt_version_id is None) -
    representing "what's currently live," not a previous candidate test."""
    runs = evaluation_repository.list_runs(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset_id, limit=50)
    for run in runs:
        if run.status == "completed" and run.prompt_version_id is None:
            return run
    return None


def evaluate_prompt_candidate(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    dataset: EvaluationDataset,
    candidate_version_id: str,
    created_by: str | None = None,
    shadow_database_url: str | None = None,
) -> PromptGateResult:
    baseline_run = _latest_baseline_run(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, dataset_id=dataset.id)

    candidate_run = run_evaluation(
        db,
        dataset=dataset,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        options=EvaluationRunOptions(
            mode="mock",
            created_by=created_by,
            trigger_source="prompt_gate",
            prompt_version_override_id=candidate_version_id,
            shadow_database_url=shadow_database_url,
        ),
    )

    if candidate_run.prompt_version_id != candidate_version_id:
        raise PromptGateIntegrityError(
            f"Evaluation run {candidate_run.id} did not record prompt_version_id={candidate_version_id!r} "
            f"(recorded {candidate_run.prompt_version_id!r}) - refusing to trust this run as evidence for promotion."
        )

    candidate_summary = build_run_summary(db, run_id=candidate_run.id)
    baseline_summary = build_run_summary(db, run_id=baseline_run.id) if baseline_run is not None else None

    verdict = evaluate_gate(candidate_summary, policy=DEFAULT_POLICY, run_status=candidate_run.status, baseline=baseline_summary)
    return PromptGateResult(verdict=verdict, candidate_run_id=candidate_run.id, baseline_run_id=baseline_run.id if baseline_run is not None else None)
