"""Centralised, configurable evaluation pass/fail thresholds.

Every quality gate documented in the launch evaluation framework reads its
numbers from an `EvaluationPolicy` instance instead of a hardcoded literal
scattered through the engine/metrics/CLI. Override defaults with environment
variables so CI and a future VPS pipeline can tune the gate without a code
change.
"""

from dataclasses import dataclass
from os import getenv


def _get_float(name: str, default: float) -> float:
    raw_value = getenv(name)
    return default if raw_value is None else float(raw_value)


def _get_int(name: str, default: int) -> int:
    raw_value = getenv(name)
    return default if raw_value is None else int(raw_value)


@dataclass(frozen=True)
class EvaluationPolicy:
    # Quality thresholds. A run's aggregate metrics are compared against these;
    # falling short marks the run as failed but is not, by itself, a hard safety
    # failure unless one of the launch-critical checks below also trips.
    #
    # Defaults reflect the launch thresholds documented and justified in
    # docs/04_Engineering/Evaluation_Success_Criteria.md. Launch-critical safety
    # conditions (cross-tenant leakage, system-prompt disclosure, secret
    # exposure, unauthorised citations, unsafe HTML) are never policy
    # thresholds - they are zero-tolerance hard failures enforced directly in
    # app.evaluation.scoring, independent of these tunable quality knobs.
    min_retrieval_hit_rate: float = 0.9
    min_citation_coverage: float = 0.95
    max_fallback_rate_on_answerable: float = 0.1
    min_correct_fallback_rate_on_unanswerable: float = 0.95
    max_p95_latency_ms: int = 8000
    max_regression_tolerance: float = 0.05

    def as_dict(self) -> dict[str, float | int]:
        return {
            "min_retrieval_hit_rate": self.min_retrieval_hit_rate,
            "min_citation_coverage": self.min_citation_coverage,
            "max_fallback_rate_on_answerable": self.max_fallback_rate_on_answerable,
            "min_correct_fallback_rate_on_unanswerable": self.min_correct_fallback_rate_on_unanswerable,
            "max_p95_latency_ms": self.max_p95_latency_ms,
            "max_regression_tolerance": self.max_regression_tolerance,
        }


def load_policy_from_env() -> EvaluationPolicy:
    return EvaluationPolicy(
        min_retrieval_hit_rate=_get_float("EVAL_MIN_RETRIEVAL_HIT_RATE", 0.9),
        min_citation_coverage=_get_float("EVAL_MIN_CITATION_COVERAGE", 0.95),
        max_fallback_rate_on_answerable=_get_float("EVAL_MAX_FALLBACK_RATE_ON_ANSWERABLE", 0.1),
        min_correct_fallback_rate_on_unanswerable=_get_float("EVAL_MIN_CORRECT_FALLBACK_RATE_ON_UNANSWERABLE", 0.95),
        max_p95_latency_ms=_get_int("EVAL_MAX_P95_LATENCY_MS", 8000),
        max_regression_tolerance=_get_float("EVAL_MAX_REGRESSION_TOLERANCE", 0.05),
    )


DEFAULT_POLICY = EvaluationPolicy()
