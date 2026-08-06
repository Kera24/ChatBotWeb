"""GraderProvider abstraction (Section 2). Mirrors app.ai.providers.base's
ABC pattern (a small set of abstract methods, a `provider_key`/`display_name`
class attribute) adapted for the evaluation subsystem's simpler, separate
error hierarchy (errors.py) rather than reusing app.ai.errors.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.evaluation.graders.context import GradingContext
from app.evaluation.graders.contracts import GraderResult, PairwiseVerdict
from app.evaluation.graders.prompts import GRADER_PROMPT_VERSION
from app.evaluation.graders.rubrics import RUBRIC_VERSION, GraderDimension, RubricDefinition


class GraderProvider(ABC):
    provider_key: str
    display_name: str
    model_name: str

    @abstractmethod
    def grade(self, *, rubric: RubricDefinition, context: GradingContext) -> GraderResult:
        """Grade one (question, answer, evidence) against one rubric
        dimension. Implementations must raise GraderTimeoutError on timeout
        and GraderOutputValidationError on malformed output - never return a
        result silently guessed to satisfy the contract."""

    @abstractmethod
    def compare_pairwise(self, *, rubric: RubricDefinition, question: str, answer_a: str, answer_b: str, evidence_block: str, order_swapped: bool = False) -> PairwiseVerdict:
        """Compare two answers against one rubric dimension."""


_WORD = re.compile(r"[A-Za-z]{3,}")
_STOPWORDS = frozenset({"the", "and", "for", "are", "does", "with", "that", "this", "you", "your", "what", "how", "when", "does"})


def _keywords(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOPWORDS}


@dataclass
class MockGraderProvider(GraderProvider):
    """Deterministic, dependency-free grader for software tests and for
    running the grading pipeline end to end without a real model configured.
    Never used for a real launch calibration decision - see
    Grader_Architecture.md's "provider setup" section. Scores are produced
    by simple, deterministic lexical-overlap heuristics (not a model call),
    intentionally varied by input so tests can exercise pass/fail/edge
    behaviour realistically, unlike a provider that always returns the same
    constant score."""

    provider_key: str = "mock"
    display_name: str = "Deterministic Mock Grader"
    model_name: str = "mock-grader-v1"

    def grade(self, *, rubric: RubricDefinition, context: GradingContext) -> GraderResult:
        dimension = rubric.dimension
        answer_keywords = _keywords(context.answer)
        question_keywords = _keywords(context.question)
        evidence_keywords = _keywords(context.evidence_block())

        if dimension == GraderDimension.RELEVANCE:
            score, reason = self._overlap_score(answer_keywords, question_keywords, "question")
        elif dimension in (GraderDimension.GROUNDEDNESS, GraderDimension.FAITHFULNESS, GraderDimension.CITATION_SUPPORT):
            score, reason = self._overlap_score(answer_keywords, evidence_keywords, "evidence")
        elif dimension == GraderDimension.COMPLETENESS:
            score, reason = self._overlap_score(evidence_keywords, answer_keywords, "answer", base_set_name="evidence")
        elif dimension == GraderDimension.CLARITY:
            score, reason = self._length_score(context.answer, target_range=(20, 400), reason_ok="answer length is readable", reason_bad="answer is unusually short or long for clarity")
        elif dimension == GraderDimension.DIRECTNESS:
            score, reason = self._length_score(context.answer, target_range=(5, 200), reason_ok="answer is concise", reason_bad="answer looks padded/verbose")
        elif dimension == GraderDimension.FALLBACK_APPROPRIATENESS:
            score, reason = self._fallback_score(context)
        elif dimension == GraderDimension.CLARIFICATION_QUALITY:
            score, reason = self._clarification_score(context)
        else:
            score, reason = 0.5, "no heuristic defined for this dimension; neutral score"

        passed = score >= rubric.pass_threshold
        unsupported = () if score >= rubric.pass_threshold else ("mock heuristic found low lexical overlap",)
        supported = (reason,) if score >= rubric.pass_threshold else ()
        return GraderResult(
            dimension=dimension, score=round(score, 3), passed=passed, confidence=0.4, reason=reason,
            unsupported_claims=unsupported, supported_claims=supported,
            rubric_version=RUBRIC_VERSION,
            prompt_version=GRADER_PROMPT_VERSION, grader_provider=self.provider_key, grader_model=self.model_name,
        )

    def compare_pairwise(self, *, rubric: RubricDefinition, question: str, answer_a: str, answer_b: str, evidence_block: str, order_swapped: bool = False) -> PairwiseVerdict:
        evidence_keywords = _keywords(evidence_block)
        score_a = len(_keywords(answer_a) & evidence_keywords)
        score_b = len(_keywords(answer_b) & evidence_keywords)
        if score_a == score_b:
            verdict = "tie"
            reason = "Both answers show equal lexical overlap with the supplied evidence under the mock heuristic."
        elif score_a > score_b:
            verdict = "a_better"
            reason = "Answer A shows higher lexical overlap with the supplied evidence under the mock heuristic."
        else:
            verdict = "b_better"
            reason = "Answer B shows higher lexical overlap with the supplied evidence under the mock heuristic."
        return PairwiseVerdict(
            verdict=verdict, reason=reason, rubric_dimension=rubric.dimension.value, order_swapped=order_swapped,
            grader_provider=self.provider_key, grader_model=self.model_name, prompt_version=GRADER_PROMPT_VERSION,
        )

    @staticmethod
    def _overlap_score(a: set[str], b: set[str], other_name: str, base_set_name: str = "answer") -> tuple[float, str]:
        if not a or not b:
            return 0.0, f"no comparable keywords found between {base_set_name} and {other_name}"
        overlap = len(a & b) / max(1, len(a))
        return min(1.0, overlap), f"{overlap:.0%} of {base_set_name} keywords overlap with {other_name}"

    @staticmethod
    def _length_score(text: str, *, target_range: tuple[int, int], reason_ok: str, reason_bad: str) -> tuple[float, str]:
        length = len(text.strip())
        low, high = target_range
        if low <= length <= high:
            return 0.9, reason_ok
        return 0.3, reason_bad

    @staticmethod
    def _fallback_score(context: GradingContext) -> tuple[float, str]:
        if context.answer_state not in ("fallback", "failed"):
            return 0.0, "dimension not applicable - answer_state is not a fallback"
        has_digit = any(character.isdigit() for character in context.answer)
        if has_digit:
            return 0.2, "fallback response contains a number, which may indicate a guessed value"
        return 0.9, "fallback response contains no invented specific values"

    @staticmethod
    def _clarification_score(context: GradingContext) -> tuple[float, str]:
        if context.category != "ambiguous":
            return 0.0, "dimension not applicable - case is not in the ambiguous category"
        asks_question = "?" in context.answer
        has_digit = any(character.isdigit() for character in context.answer)
        if asks_question and not has_digit:
            return 0.8, "response asks a clarifying question rather than guessing a specific value"
        return 0.3, "response does not clearly request the missing detail"
