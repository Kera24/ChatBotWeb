"""Release gate: decide whether a completed evaluation run is safe to ship.

Deployment-agnostic on purpose - this only inspects a `RunSummary`/policy and
returns a verdict object with a plain boolean and reasons. The CLI turns that
into a process exit code; a future CI workflow (GitHub Actions today, a VPS
pipeline later) just needs to run the CLI and check its exit code, so this
module never talks to any specific CI or cloud provider.
"""

from dataclasses import dataclass

from app.evaluation.metrics.aggregate import RunSummary, compare_to_baseline
from app.evaluation.policy import EvaluationPolicy


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    reasons: list[str]

    def as_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "reasons": self.reasons}


def evaluate_gate(
    summary: RunSummary,
    *,
    policy: EvaluationPolicy,
    run_status: str,
    baseline: RunSummary | None = None,
) -> GateVerdict:
    reasons: list[str] = []

    if run_status != "completed":
        reasons.append(f"run did not complete (status={run_status})")
    if summary.hard_failure_cases > 0:
        reasons.append(f"{summary.hard_failure_cases} launch-critical hard failure(s)")
    if summary.retrieval_hit_rate is not None and summary.retrieval_hit_rate < policy.min_retrieval_hit_rate:
        reasons.append(f"retrieval hit rate {summary.retrieval_hit_rate:.2f} below minimum {policy.min_retrieval_hit_rate:.2f}")
    if summary.citation_coverage < policy.min_citation_coverage:
        reasons.append(f"citation coverage {summary.citation_coverage:.2f} below minimum {policy.min_citation_coverage:.2f}")
    if summary.fallback_rate_on_answerable is not None and summary.fallback_rate_on_answerable > policy.max_fallback_rate_on_answerable:
        reasons.append(f"fallback rate on answerable cases {summary.fallback_rate_on_answerable:.2f} above maximum {policy.max_fallback_rate_on_answerable:.2f}")
    if (
        summary.correct_fallback_rate_on_unanswerable is not None
        and summary.correct_fallback_rate_on_unanswerable < policy.min_correct_fallback_rate_on_unanswerable
    ):
        reasons.append(
            f"correct fallback rate on unanswerable cases {summary.correct_fallback_rate_on_unanswerable:.2f} "
            f"below minimum {policy.min_correct_fallback_rate_on_unanswerable:.2f}"
        )
    if summary.latency_p95_ms is not None and summary.latency_p95_ms > policy.max_p95_latency_ms:
        reasons.append(f"p95 latency {summary.latency_p95_ms:.0f}ms above maximum {policy.max_p95_latency_ms}ms")

    if baseline is not None:
        comparison = compare_to_baseline(summary, baseline)
        pass_rate_drop = baseline.pass_rate - summary.pass_rate
        if pass_rate_drop > policy.max_regression_tolerance:
            reasons.append(f"pass rate dropped {pass_rate_drop:.2%} versus baseline, exceeding tolerance {policy.max_regression_tolerance:.2%}")
        if comparison["candidate_hard_failure_cases"] > comparison["baseline_hard_failure_cases"]:
            reasons.append("hard failures increased versus baseline")

    return GateVerdict(passed=len(reasons) == 0, reasons=reasons)
