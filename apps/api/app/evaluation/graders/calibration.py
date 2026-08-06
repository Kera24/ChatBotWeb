"""Runs graders against the human-reviewed calibration set (Section 7/8) and
reports agreement with human labels. Standalone from the evaluation-run
database entirely - the calibration set is a fixture file, not persisted
EvaluationResult rows, so this can run without a seeded dataset.

Section 8's explicit requirement: "Do not make a grader launch-gating unless
calibration meets an explicit threshold." That threshold is defined here as
_CALIBRATION_PASS_AGREEMENT_THRESHOLD and documented in
Grader_Architecture.md's "Advisory vs gating policy" section - no rubric
dimension in rubrics.py is marked gating=True today, so this threshold has
not yet been met/exercised for a real gating decision; it exists so a future
calibration run has an unambiguous bar to clear.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.evaluation.graders.context import EvidenceItem, GradingContext
from app.evaluation.graders.provider import GraderProvider
from app.evaluation.graders.rubrics import GraderDimension, get_rubric

CALIBRATION_SET_PATH = Path(__file__).resolve().parents[2] / "evaluation" / "fixtures" / "calibration_set.json"

_CALIBRATION_PASS_AGREEMENT_THRESHOLD = 0.8  # a grader dimension may only be proposed as gating once its calibration agreement-with-human-labels reaches this bar


@dataclass
class CalibrationExampleResult:
    example_id: str
    dimension: str
    human_passed: bool
    grader_passed: bool | None
    human_score_band: tuple[float, float]
    grader_score: float | None
    agrees: bool
    error: str | None = None


@dataclass
class CalibrationReport:
    total_examples: int
    per_dimension: dict[str, list[CalibrationExampleResult]] = field(default_factory=dict)

    def agreement_rate(self, dimension: str | None = None) -> float | None:
        rows = self._rows(dimension)
        graded = [r for r in rows if r.error is None]
        if not graded:
            return None
        return sum(1 for r in graded if r.agrees) / len(graded)

    def false_positives(self, dimension: str | None = None) -> list[CalibrationExampleResult]:
        return [r for r in self._rows(dimension) if r.error is None and r.grader_passed and not r.human_passed]

    def false_negatives(self, dimension: str | None = None) -> list[CalibrationExampleResult]:
        return [r for r in self._rows(dimension) if r.error is None and not r.grader_passed and r.human_passed]

    def score_bias(self, dimension: str | None = None) -> float | None:
        rows = [r for r in self._rows(dimension) if r.error is None and r.grader_score is not None]
        if not rows:
            return None
        midpoints = [(r.human_score_band[0] + r.human_score_band[1]) / 2 for r in rows]
        deltas = [row.grader_score - midpoint for row, midpoint in zip(rows, midpoints)]
        return sum(deltas) / len(deltas)

    def meets_gating_threshold(self, dimension: str) -> bool:
        rate = self.agreement_rate(dimension)
        return rate is not None and rate >= _CALIBRATION_PASS_AGREEMENT_THRESHOLD

    def _rows(self, dimension: str | None) -> list[CalibrationExampleResult]:
        if dimension is not None:
            return self.per_dimension.get(dimension, [])
        return [row for rows in self.per_dimension.values() for row in rows]

    def as_dict(self) -> dict:
        return {
            "total_examples": self.total_examples,
            "calibration_gating_threshold": _CALIBRATION_PASS_AGREEMENT_THRESHOLD,
            "dimensions": {
                dim: {
                    "agreement_rate": self.agreement_rate(dim),
                    "false_positives": len(self.false_positives(dim)),
                    "false_negatives": len(self.false_negatives(dim)),
                    "score_bias": self.score_bias(dim),
                    "meets_gating_threshold": self.meets_gating_threshold(dim),
                    "examples": [
                        {"id": r.example_id, "human_passed": r.human_passed, "grader_passed": r.grader_passed, "agrees": r.agrees, "error": r.error}
                        for r in rows
                    ],
                }
                for dim, rows in self.per_dimension.items()
            },
        }


def load_calibration_set() -> list[dict]:
    import json
    with open(CALIBRATION_SET_PATH, encoding="utf-8") as f:
        return json.load(f)["examples"]


def run_calibration(*, provider: GraderProvider) -> CalibrationReport:
    examples = load_calibration_set()
    per_dimension: dict[str, list[CalibrationExampleResult]] = {}

    for example in examples:
        dimension = GraderDimension(example["rubric_dimension"])
        rubric = get_rubric(dimension)
        context = GradingContext(
            question=example["question"], answer=example["answer"], answer_state=example["answer_state"],
            category=example["category"], expected_answerability=example.get("expected_answerability", "answerable"),
            reference_answer=example.get("reference_answer"),
            evidence=tuple(EvidenceItem(evidence_id=e["evidence_id"], chunk_id=e["evidence_id"], document_title=e["document_title"], content=e["content"]) for e in example.get("evidence", [])),
        )
        human_label = example["human_label"]
        human_passed = human_label["passed"]
        score_band = tuple(human_label["score_band"])

        try:
            grader_result = provider.grade(rubric=rubric, context=context)
            grader_passed = grader_result.passed
            grader_score = grader_result.score
            error = None
        except Exception as exc:  # noqa: BLE001 - calibration must never crash on one bad example; record and continue
            grader_passed, grader_score, error = None, None, str(exc)

        row = CalibrationExampleResult(
            example_id=example["id"], dimension=dimension.value, human_passed=human_passed, grader_passed=grader_passed,
            human_score_band=score_band, grader_score=grader_score, agrees=(grader_passed == human_passed) if error is None else False, error=error,
        )
        per_dimension.setdefault(dimension.value, []).append(row)

    return CalibrationReport(total_examples=len(examples), per_dimension=per_dimension)
