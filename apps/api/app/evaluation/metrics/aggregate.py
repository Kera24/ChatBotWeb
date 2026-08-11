"""Run-level aggregation used for the terminal report, the JSON report, the API
run-summary endpoint, and the regression gate.
"""

from dataclasses import dataclass, field
from statistics import median


@dataclass(frozen=True)
class CaseSummary:
    case_id: str
    question: str
    category: str
    passed: bool
    hard_failure: bool
    failure_reasons: list[str]
    latency_ms: int | None


@dataclass(frozen=True)
class RunSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    hard_failure_cases: int
    pass_rate: float
    retrieval_hit_rate: float | None
    citation_coverage: float
    fallback_rate_on_answerable: float | None
    correct_fallback_rate_on_unanswerable: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    category_breakdown: dict[str, dict[str, int]]
    average_duplicate_context_rate: float | None = None
    average_precision_at_k: float | None = None
    average_recall_at_k: float | None = None
    unauthorised_source_rate: float | None = None
    invalid_citation_rate: float | None = None
    # Retrieval V2 Phase 1 (docs/future/HybridRetrieval.md) bake-off fields.
    average_evidence_coverage: float | None = None
    retrieval_strategy: str | None = None
    average_dense_candidate_count: float | None = None
    average_lexical_candidate_count: float | None = None
    average_fused_candidate_count: float | None = None
    average_dense_latency_ms: float | None = None
    average_lexical_latency_ms: float | None = None
    average_fusion_latency_ms: float | None = None
    failed_cases_list: list[CaseSummary] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "hard_failure_cases": self.hard_failure_cases,
            "pass_rate": self.pass_rate,
            "retrieval_hit_rate": self.retrieval_hit_rate,
            "citation_coverage": self.citation_coverage,
            "fallback_rate_on_answerable": self.fallback_rate_on_answerable,
            "correct_fallback_rate_on_unanswerable": self.correct_fallback_rate_on_unanswerable,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "average_duplicate_context_rate": self.average_duplicate_context_rate,
            "average_precision_at_k": self.average_precision_at_k,
            "average_recall_at_k": self.average_recall_at_k,
            "unauthorised_source_rate": self.unauthorised_source_rate,
            "invalid_citation_rate": self.invalid_citation_rate,
            "average_evidence_coverage": self.average_evidence_coverage,
            "retrieval_strategy": self.retrieval_strategy,
            "average_dense_candidate_count": self.average_dense_candidate_count,
            "average_lexical_candidate_count": self.average_lexical_candidate_count,
            "average_fused_candidate_count": self.average_fused_candidate_count,
            "average_dense_latency_ms": self.average_dense_latency_ms,
            "average_lexical_latency_ms": self.average_lexical_latency_ms,
            "average_fusion_latency_ms": self.average_fusion_latency_ms,
            "category_breakdown": self.category_breakdown,
            "failed_case_details": [
                {
                    "case_id": item.case_id,
                    "question": item.question,
                    "category": item.category,
                    "passed": item.passed,
                    "hard_failure": item.hard_failure,
                    "failure_reasons": item.failure_reasons,
                    "latency_ms": item.latency_ms,
                }
                for item in self.failed_cases_list
            ],
        }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = percentile * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarise_results(results: list[dict]) -> RunSummary:
    """`results` is a list of plain dicts shaped like an EvaluationResult row
    plus its case's category/question/expected_answerability, so this module
    stays independent of the ORM layer and is trivially unit-testable."""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    hard_failures = sum(1 for r in results if r["hard_failure"])
    failed = total - passed

    latencies = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    prompt_tokens = sum(r.get("prompt_tokens") or 0 for r in results)
    completion_tokens = sum(r.get("completion_tokens") or 0 for r in results)
    total_tokens = sum(r.get("total_tokens") or 0 for r in results)

    hit_flags = [r["retrieval_metrics"].get("expected_document_retrieved") for r in results if r["retrieval_metrics"].get("expected_document_retrieved") is not None]
    retrieval_hit_rate = (sum(1 for value in hit_flags if value) / len(hit_flags)) if hit_flags else None

    citation_required_or_present = [r for r in results if r["answer_metrics"].get("answer_produced")]
    citation_coverage = (
        sum(1 for r in citation_required_or_present if r["answer_metrics"].get("citation_present")) / len(citation_required_or_present)
        if citation_required_or_present
        else 0.0
    )

    answerable = [r for r in results if r["expected_answerability"] == "answerable"]
    fallback_rate_on_answerable = (
        sum(1 for r in answerable if r["answer_state"] in {"fallback", "failed"}) / len(answerable) if answerable else None
    )

    unanswerable = [r for r in results if r["expected_answerability"] == "unanswerable"]
    correct_fallback_rate_on_unanswerable = (
        sum(1 for r in unanswerable if r["answer_state"] in {"fallback", "failed"}) / len(unanswerable) if unanswerable else None
    )

    duplicate_rates = [r["retrieval_metrics"].get("duplicate_context_rate") for r in results if r["retrieval_metrics"].get("duplicate_context_rate") is not None]
    average_duplicate_context_rate = (sum(duplicate_rates) / len(duplicate_rates)) if duplicate_rates else None

    precision_values = [r["retrieval_metrics"].get("precision_at_k") for r in results if r["retrieval_metrics"].get("precision_at_k") is not None]
    average_precision_at_k = (sum(precision_values) / len(precision_values)) if precision_values else None

    recall_values = [r["retrieval_metrics"].get("recall_at_k") for r in results if r["retrieval_metrics"].get("recall_at_k") is not None]
    average_recall_at_k = (sum(recall_values) / len(recall_values)) if recall_values else None

    evidence_coverage_values = [
        r["retrieval_metrics"].get("evidence_coverage") for r in results if r["retrieval_metrics"].get("evidence_coverage") is not None
    ]
    average_evidence_coverage = (sum(evidence_coverage_values) / len(evidence_coverage_values)) if evidence_coverage_values else None

    strategies = [r["retrieval_metrics"].get("retrieval_strategy") for r in results if r["retrieval_metrics"].get("retrieval_strategy")]
    retrieval_strategy = strategies[0] if strategies else None

    def _average(field_name: str) -> float | None:
        values = [r["retrieval_metrics"].get(field_name) for r in results if r["retrieval_metrics"].get(field_name) is not None]
        return (sum(values) / len(values)) if values else None

    average_dense_candidate_count = _average("dense_candidate_count")
    average_lexical_candidate_count = _average("lexical_candidate_count")
    average_fused_candidate_count = _average("fused_candidate_count")
    average_dense_latency_ms = _average("dense_latency_ms")
    average_lexical_latency_ms = _average("lexical_latency_ms")
    average_fusion_latency_ms = _average("fusion_latency_ms")

    unauthorised_source_flags = [r for r in results if r["retrieval_metrics"]]
    unauthorised_source_rate = (
        sum(1 for r in unauthorised_source_flags if r["retrieval_metrics"].get("unauthorised_source_failure")) / len(unauthorised_source_flags)
        if unauthorised_source_flags
        else None
    )

    invalid_citation_flags = [r for r in results if r["answer_metrics"]]
    invalid_citation_rate = (
        sum(1 for r in invalid_citation_flags if r["answer_metrics"].get("unsupported_citation_identifier")) / len(invalid_citation_flags)
        if invalid_citation_flags
        else None
    )

    category_breakdown: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = category_breakdown.setdefault(r["category"], {"total": 0, "passed": 0, "failed": 0, "hard_failure": 0})
        bucket["total"] += 1
        bucket["passed" if r["passed"] else "failed"] += 1
        if r["hard_failure"]:
            bucket["hard_failure"] += 1

    failed_cases_list = [
        CaseSummary(
            case_id=r["case_id"],
            question=r["question"],
            category=r["category"],
            passed=r["passed"],
            hard_failure=r["hard_failure"],
            failure_reasons=r["failure_reasons"],
            latency_ms=r.get("latency_ms"),
        )
        for r in results
        if not r["passed"]
    ]

    return RunSummary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=failed,
        hard_failure_cases=hard_failures,
        pass_rate=(passed / total) if total else 0.0,
        retrieval_hit_rate=retrieval_hit_rate,
        citation_coverage=citation_coverage,
        fallback_rate_on_answerable=fallback_rate_on_answerable,
        correct_fallback_rate_on_unanswerable=correct_fallback_rate_on_unanswerable,
        latency_p50_ms=_percentile([float(v) for v in latencies], 0.5),
        latency_p95_ms=_percentile([float(v) for v in latencies], 0.95),
        total_prompt_tokens=prompt_tokens,
        total_completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        category_breakdown=category_breakdown,
        average_duplicate_context_rate=average_duplicate_context_rate,
        average_precision_at_k=average_precision_at_k,
        average_recall_at_k=average_recall_at_k,
        unauthorised_source_rate=unauthorised_source_rate,
        invalid_citation_rate=invalid_citation_rate,
        average_evidence_coverage=average_evidence_coverage,
        retrieval_strategy=retrieval_strategy,
        average_dense_candidate_count=average_dense_candidate_count,
        average_lexical_candidate_count=average_lexical_candidate_count,
        average_fused_candidate_count=average_fused_candidate_count,
        average_dense_latency_ms=average_dense_latency_ms,
        average_lexical_latency_ms=average_lexical_latency_ms,
        average_fusion_latency_ms=average_fusion_latency_ms,
        failed_cases_list=failed_cases_list,
    )


def compare_to_baseline(candidate: RunSummary, baseline: RunSummary) -> dict[str, object]:
    return {
        "baseline_pass_rate": baseline.pass_rate,
        "candidate_pass_rate": candidate.pass_rate,
        "pass_rate_delta": candidate.pass_rate - baseline.pass_rate,
        "baseline_hard_failure_cases": baseline.hard_failure_cases,
        "candidate_hard_failure_cases": candidate.hard_failure_cases,
        "baseline_latency_p95_ms": baseline.latency_p95_ms,
        "candidate_latency_p95_ms": candidate.latency_p95_ms,
        "regressed": candidate.pass_rate < baseline.pass_rate or candidate.hard_failure_cases > baseline.hard_failure_cases,
    }
