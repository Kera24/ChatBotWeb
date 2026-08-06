"""Grading report builder (Section 11) - dimension averages, pass rates,
score distributions, claim/citation findings, consistency, and a clearly
labelled disclaimer that every score is a model-generated estimate, never
objective truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models.evaluation import EvaluationCase
from app.repositories import evaluation_repository


@dataclass
class DimensionSummary:
    dimension: str
    graded_count: int = 0
    error_count: int = 0
    pass_count: int = 0
    scores: list[float] = field(default_factory=list)

    @property
    def average_score(self) -> float | None:
        return sum(self.scores) / len(self.scores) if self.scores else None

    @property
    def pass_rate(self) -> float | None:
        return self.pass_count / self.graded_count if self.graded_count else None

    def as_dict(self) -> dict:
        return {
            "dimension": self.dimension, "graded_count": self.graded_count, "error_count": self.error_count,
            "average_score": self.average_score, "pass_rate": self.pass_rate,
            "score_distribution": _bucket(self.scores),
        }


def _bucket(scores: list[float]) -> dict[str, int]:
    buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for score in scores:
        if score < 0.2:
            buckets["0.0-0.2"] += 1
        elif score < 0.4:
            buckets["0.2-0.4"] += 1
        elif score < 0.6:
            buckets["0.4-0.6"] += 1
        elif score < 0.8:
            buckets["0.6-0.8"] += 1
        else:
            buckets["0.8-1.0"] += 1
    return buckets


@dataclass
class GradingRunSummary:
    run_id: str
    graded_result_count: int
    dimensions: dict[str, DimensionSummary]
    low_confidence_cases: list[dict]
    deterministic_disagreements: list[dict]

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "graded_result_count": self.graded_result_count,
            "disclaimer": "All scores below are model-generated estimates from an LLM grader, not objective truth. Advisory only - see Grader_Architecture.md for the advisory/gating policy.",
            "dimensions": {name: summary.as_dict() for name, summary in self.dimensions.items()},
            "low_confidence_cases": self.low_confidence_cases,
            "deterministic_vs_grader_disagreement": self.deterministic_disagreements,
        }


_LOW_CONFIDENCE_THRESHOLD = 0.3


def build_grading_summary(db: Session, *, run_id: str) -> GradingRunSummary:
    results = evaluation_repository.list_results_for_run(db, run_id=run_id)
    dimensions: dict[str, DimensionSummary] = {}
    low_confidence_cases: list[dict] = []
    disagreements: list[dict] = []
    graded_count = 0

    for result in results:
        payload = result.judge_scores_json
        if not payload:
            continue
        graded_count += 1
        case = db.get(EvaluationCase, result.case_id)
        for dim_name, dim_payload in (payload.get("dimensions") or {}).items():
            summary = dimensions.setdefault(dim_name, DimensionSummary(dimension=dim_name))
            if "error" in dim_payload:
                summary.error_count += 1
                continue
            summary.graded_count += 1
            score = dim_payload.get("score")
            if score is not None:
                summary.scores.append(score)
            if dim_payload.get("passed"):
                summary.pass_count += 1
            if (dim_payload.get("confidence") or 1.0) < _LOW_CONFIDENCE_THRESHOLD:
                low_confidence_cases.append({"case_id": result.case_id, "question": case.question if case else None, "dimension": dim_name, "confidence": dim_payload.get("confidence")})
            # Deterministic-vs-grader disagreement: a deterministic hard failure but the grader still passed the answer, or vice versa.
            if result.hard_failure and dim_payload.get("passed") and dim_name in ("groundedness", "citation_support"):
                disagreements.append({
                    "case_id": result.case_id, "question": case.question if case else None, "dimension": dim_name,
                    "deterministic_hard_failure": True, "grader_passed": True,
                    "note": "Deterministic gate marked this a hard failure but the grader passed it - deterministic gate remains authoritative.",
                })

    return GradingRunSummary(run_id=run_id, graded_result_count=graded_count, dimensions=dimensions, low_confidence_cases=low_confidence_cases, deterministic_disagreements=disagreements)


def render_grading_text_report(summary: GradingRunSummary) -> str:
    lines = [
        f"Grading report for run {summary.run_id}",
        "All scores are model-generated estimates, not objective truth.",
        f"Graded results: {summary.graded_result_count}",
        "",
    ]
    for name, dim in sorted(summary.dimensions.items()):
        avg = f"{dim.average_score:.2f}" if dim.average_score is not None else "n/a"
        pass_rate = f"{dim.pass_rate:.1%}" if dim.pass_rate is not None else "n/a"
        lines.append(f"  {name:<28} avg={avg:<6} pass_rate={pass_rate:<8} graded={dim.graded_count} errors={dim.error_count}")
    if summary.low_confidence_cases:
        lines.append("")
        lines.append(f"Low-confidence findings (< {_LOW_CONFIDENCE_THRESHOLD}): {len(summary.low_confidence_cases)} (see JSON report for detail - human review recommended)")
    if summary.deterministic_disagreements:
        lines.append("")
        lines.append(f"Deterministic-vs-grader disagreements: {len(summary.deterministic_disagreements)} (deterministic gate remains authoritative)")
    return "\n".join(lines)
