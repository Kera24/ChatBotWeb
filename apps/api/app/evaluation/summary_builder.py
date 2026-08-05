"""Build a `RunSummary` from persisted EvaluationResult rows for a run.

Shared by the API router and the CLI so both read the exact same shape.
"""

from sqlalchemy.orm import Session

from app.db.models import EvaluationCase
from app.evaluation.metrics.aggregate import RunSummary, summarise_results
from app.repositories import evaluation_repository


def build_run_summary(db: Session, *, run_id: str) -> RunSummary:
    results = evaluation_repository.list_results_for_run(db, run_id=run_id)
    rows = []
    for result in results:
        case: EvaluationCase | None = result.case
        rows.append({
            "case_id": result.case_id,
            "question": case.question if case is not None else "",
            "category": case.category if case is not None else "unknown",
            "expected_answerability": case.expected_answerability if case is not None else "answerable",
            "passed": result.passed,
            "hard_failure": result.hard_failure,
            "failure_reasons": result.failure_reasons_json or [],
            "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "answer_state": result.answer_state,
            "retrieval_metrics": result.retrieval_metrics_json or {},
            "answer_metrics": result.answer_metrics_json or {},
        })
    return summarise_results(rows)
