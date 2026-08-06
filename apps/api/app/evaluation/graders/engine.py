"""Grading orchestration: builds a GradingContext from a persisted
EvaluationResult, calls a GraderProvider per requested dimension, measures
consistency via repeated grading, and writes results back to
EvaluationResult.judge_scores_json (Section 9 - the existing nullable JSON
column, unused until now, reused rather than adding a migration).

Deliberately evaluation-time only: nothing here is imported by
app.ai.rag_orchestrator or called during a live request (Section 13's "no
grader should run automatically on every production request at launch").
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.chunk import Chunk
from app.db.models.document import Document
from app.db.models.evaluation import EvaluationCase, EvaluationResult
from app.evaluation.graders.claims import deterministic_value_support, extract_claims
from app.evaluation.graders.contracts import ConsistencyReport, GraderResult, PairwiseVerdict
from app.evaluation.graders.context import EvidenceItem, GradingContext
from app.evaluation.graders.errors import GraderOutputValidationError, GraderProviderError, GraderTimeoutError
from app.evaluation.graders.cache import GraderResultCache, cache_key
from app.evaluation.graders.provider import GraderProvider
from app.evaluation.redaction import redact_secrets
from app.evaluation.graders.rubrics import RUBRICS, GraderDimension, RubricDefinition, get_rubric
from app.repositories import evaluation_repository

_CONSISTENCY_VARIANCE_THRESHOLD = 0.05  # score variance above this across repetitions marks a dimension inconsistent for this run - see Section 6


@dataclass
class GradedDimensionOutcome:
    result: GraderResult | None
    error: str | None = None
    consistency: ConsistencyReport | None = None
    from_cache: bool = False


@dataclass
class GradingRunStats:
    total_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_latency_ms: float = 0.0
    errors: int = 0
    graded_cases: int = 0


@dataclass
class GradedResultOutcome:
    result_id: str
    case_id: str
    question: str
    dimensions: dict[str, GradedDimensionOutcome] = field(default_factory=dict)


def _dimensions_applicable(rubric: RubricDefinition, context: GradingContext) -> bool:
    if rubric.dimension == GraderDimension.FALLBACK_APPROPRIATENESS:
        return context.answer_state in ("fallback", "failed")
    if rubric.dimension == GraderDimension.CLARIFICATION_QUALITY:
        return context.category == "ambiguous"
    if rubric.dimension in (GraderDimension.CITATION_SUPPORT,):
        return context.answer_state == "answered" and bool(context.evidence)
    return context.answer_state == "answered"


def build_grading_context(db: Session, *, result: EvaluationResult, case: EvaluationCase) -> GradingContext:
    """Assembles evidence strictly from what this result actually cited -
    the same authorised, assistant-scoped chunks the answer was generated
    from, never a fresh unrestricted query (Section 3's scoping
    requirement). No system prompt, credentials, or other tenants' data is
    ever included."""
    evidence: list[EvidenceItem] = []
    for citation in result.citations_json or []:
        chunk_id = citation.get("chunk_id")
        chunk = db.get(Chunk, chunk_id) if chunk_id else None
        if chunk is None:
            continue
        document = db.get(Document, chunk.document_id)
        evidence.append(EvidenceItem(
            evidence_id=str(citation.get("citation_index", len(evidence) + 1)),
            chunk_id=chunk_id,
            document_title=document.title if document else (citation.get("source_title") or ""),
            content=chunk.content,
        ))
    return GradingContext(
        question=redact_secrets(case.question) or case.question,
        answer=redact_secrets(result.actual_answer or "") or "",
        answer_state=result.answer_state or "unknown",
        category=case.category,
        expected_answerability=case.expected_answerability,
        reference_answer=case.reference_answer,
        evidence=tuple(evidence),
    )


def grade_one_dimension(
    *, provider: GraderProvider, rubric: RubricDefinition, context: GradingContext,
    repetitions: int = 1, cache: GraderResultCache | None = None, stats: GradingRunStats | None = None,
) -> GradedDimensionOutcome:
    stats = stats or GradingRunStats()
    if not _dimensions_applicable(rubric, context):
        return GradedDimensionOutcome(result=None, error=None)

    key = cache_key(dimension=rubric.dimension, context=context, rubric_version=rubric.dimension.value, grader_model=provider.model_name)
    if cache is not None and repetitions == 1:
        cached = cache.get(key)
        if cached is not None:
            return GradedDimensionOutcome(result=cached, from_cache=True)

    results: list[GraderResult] = []
    last_error: str | None = None
    for _ in range(max(1, repetitions)):
        started = time.monotonic()
        try:
            stats.total_calls += 1
            outcome = provider.grade(rubric=rubric, context=context)
            results.append(outcome)
        except (GraderTimeoutError, GraderProviderError, GraderOutputValidationError) as exc:
            stats.errors += 1
            last_error = redact_secrets(str(exc)) or exc.__class__.__name__
        finally:
            stats.total_latency_ms += (time.monotonic() - started) * 1000

    if not results:
        return GradedDimensionOutcome(result=None, error=last_error or "grader produced no result")

    consistency = None
    if repetitions > 1:
        consistency = _measure_consistency(rubric.dimension, results)

    final_result = results[0]
    if cache is not None and repetitions == 1:
        cache.set(key, final_result)
    return GradedDimensionOutcome(result=final_result, error=None, consistency=consistency)


def _measure_consistency(dimension: GraderDimension, results: list[GraderResult]) -> ConsistencyReport:
    scores = tuple(r.score for r in results)
    pass_votes = [r.passed for r in results]
    majority = sum(pass_votes) >= len(pass_votes) / 2
    agreement_rate = sum(1 for vote in pass_votes if vote == majority) / len(pass_votes)
    variance = statistics.pvariance(scores) if len(scores) > 1 else 0.0
    return ConsistencyReport(
        dimension=dimension, repetitions=len(results), scores=scores, agreement_rate=agreement_rate,
        score_variance=variance, is_consistent=variance <= _CONSISTENCY_VARIANCE_THRESHOLD,
    )


def grade_result(
    db: Session, *, result: EvaluationResult, case: EvaluationCase, provider: GraderProvider,
    dimensions: tuple[GraderDimension, ...] | None = None, repetitions: int = 1,
    cache: GraderResultCache | None = None, stats: GradingRunStats | None = None, persist: bool = True,
) -> GradedResultOutcome:
    stats = stats or GradingRunStats()
    dimensions = dimensions or tuple(RUBRICS.keys())
    context = build_grading_context(db, result=result, case=case)

    outcome = GradedResultOutcome(result_id=result.id, case_id=case.id, question=case.question)
    for dimension in dimensions:
        rubric = get_rubric(dimension)
        outcome.dimensions[dimension.value] = grade_one_dimension(
            provider=provider, rubric=rubric, context=context, repetitions=repetitions, cache=cache, stats=stats,
        )
    stats.graded_cases += 1

    if persist:
        _persist_grading_outcome(db, result=result, provider=provider, outcome=outcome)
    return outcome


def _persist_grading_outcome(db: Session, *, result: EvaluationResult, provider: GraderProvider, outcome: GradedResultOutcome) -> None:
    """Never overwrites deterministic fields (passed/hard_failure/failure_reasons_json
    etc.) - only judge_scores_json, which is nullable and dedicated to
    grader output (Section 9's 'deterministic results remain separate' /
    'grader failures do not invalidate deterministic evidence').

    Merges into any existing judge_scores_json rather than replacing it
    wholesale, so a focused rerun (e.g. --dimension groundedness
    --failed-only, or a rerun with a different provider) adds/updates only
    the dimensions it actually touched, never silently discarding a prior
    grading pass's other dimensions (Section 9's "reruns can use different
    graders without overwriting old results")."""
    existing = result.judge_scores_json or {}
    dimensions = dict(existing.get("dimensions") or {})
    for dimension_name, dim_outcome in outcome.dimensions.items():
        if dim_outcome.result is not None:
            dimensions[dimension_name] = {
                **dim_outcome.result.model_dump(),
                "from_cache": dim_outcome.from_cache,
                "consistency": dim_outcome.consistency.model_dump() if dim_outcome.consistency else None,
            }
        elif dim_outcome.error is not None:
            dimensions[dimension_name] = {"error": dim_outcome.error, "is_model_generated_estimate": True}
        # else: dimension not applicable to this case - left untouched (not overwritten, not recorded as a failure)
    payload = {
        "grader_provider": provider.provider_key,
        "grader_model": provider.model_name,
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "dimensions": dimensions,
    }
    evaluation_repository.update_result(db, result=result, updates={"judge_scores_json": payload})


def compare_pairwise_with_swap_check(
    *, provider: GraderProvider, rubric: RubricDefinition, question: str, answer_baseline: str, answer_candidate: str, evidence_block: str,
) -> tuple[PairwiseVerdict, PairwiseVerdict, bool]:
    """Runs the comparison twice - once as (baseline=A, candidate=B), once
    swapped (candidate=A, baseline=B) - and reports whether the verdict was
    consistent after accounting for the swap (Section 5's position-bias
    prevention). Returns (forward_verdict, swapped_verdict, is_consistent)."""
    forward = provider.compare_pairwise(rubric=rubric, question=question, answer_a=answer_baseline, answer_b=answer_candidate, evidence_block=evidence_block, order_swapped=False)
    swapped = provider.compare_pairwise(rubric=rubric, question=question, answer_a=answer_candidate, answer_b=answer_baseline, evidence_block=evidence_block, order_swapped=True)

    def _normalise(verdict: PairwiseVerdict, is_swapped: bool) -> str:
        if verdict.verdict in ("tie", "both_unacceptable"):
            return verdict.verdict
        if not is_swapped:
            return "baseline_better" if verdict.verdict == "a_better" else "candidate_better"
        return "candidate_better" if verdict.verdict == "a_better" else "baseline_better"

    consistent = _normalise(forward, False) == _normalise(swapped, True)
    return forward, swapped, consistent


def claim_level_findings(*, answer: str, context: GradingContext) -> list[dict]:
    """Deterministic claim/evidence support pass (Section 4) - runs
    independently of any grader call, using the same value-extractor
    machinery already validated for the evidence-sufficiency guardrail."""
    evidence_text = context.evidence_block()
    findings = []
    for claim in extract_claims(answer):
        deterministic_supported = deterministic_value_support(claim, evidence_text)
        findings.append({
            "claim_text": claim.text,
            "cited_evidence_ids": list(claim.cited_evidence_ids),
            "has_checkable_values": deterministic_supported is not None,
            "deterministic_value_supported": deterministic_supported,
        })
    return findings
