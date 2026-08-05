import pytest

from app.evaluation.gate import evaluate_gate
from app.evaluation.metrics.aggregate import summarise_results
from app.evaluation.policy import DEFAULT_POLICY, EvaluationPolicy, load_policy_from_env


def _row(**overrides) -> dict:
    base = {
        "case_id": "case-1",
        "question": "Q?",
        "category": "answerable_factual",
        "expected_answerability": "answerable",
        "passed": True,
        "hard_failure": False,
        "failure_reasons": [],
        "latency_ms": 100,
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
        "answer_state": "answered",
        "retrieval_metrics": {"expected_document_retrieved": True},
        "answer_metrics": {"answer_produced": True, "citation_present": True},
    }
    base.update(overrides)
    return base


def test_default_policy_launch_thresholds_match_success_criteria() -> None:
    """Regression test for the launch-threshold strengthening documented in
    docs/04_Engineering/Evaluation_Success_Criteria.md - these must never be
    silently lowered."""
    assert DEFAULT_POLICY.min_retrieval_hit_rate == 0.9
    assert DEFAULT_POLICY.min_citation_coverage == 0.95
    assert DEFAULT_POLICY.min_correct_fallback_rate_on_unanswerable == 0.95
    assert DEFAULT_POLICY.max_fallback_rate_on_answerable == 0.1
    assert DEFAULT_POLICY.max_p95_latency_ms == 8000


def test_load_policy_from_env_uses_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "EVAL_MIN_RETRIEVAL_HIT_RATE", "EVAL_MIN_CITATION_COVERAGE", "EVAL_MAX_FALLBACK_RATE_ON_ANSWERABLE",
        "EVAL_MIN_CORRECT_FALLBACK_RATE_ON_UNANSWERABLE", "EVAL_MAX_P95_LATENCY_MS", "EVAL_MAX_REGRESSION_TOLERANCE",
    ]:
        monkeypatch.delenv(name, raising=False)
    policy = load_policy_from_env()
    assert policy == DEFAULT_POLICY


def test_load_policy_from_env_reads_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_MIN_RETRIEVAL_HIT_RATE", "0.5")
    monkeypatch.setenv("EVAL_MAX_P95_LATENCY_MS", "3000")
    policy = load_policy_from_env()
    assert policy.min_retrieval_hit_rate == 0.5
    assert policy.max_p95_latency_ms == 3000


def test_gate_passes_a_clean_completed_run() -> None:
    summary = summarise_results([_row(), _row(case_id="case-2")])
    verdict = evaluate_gate(summary, policy=DEFAULT_POLICY, run_status="completed")
    assert verdict.passed is True
    assert verdict.reasons == []


def test_gate_fails_on_any_hard_failure_regardless_of_policy_thresholds() -> None:
    summary = summarise_results([_row(hard_failure=True, passed=False, failure_reasons=["cross_tenant_leakage"])])
    lenient_policy = EvaluationPolicy(min_retrieval_hit_rate=0.0, min_citation_coverage=0.0, max_fallback_rate_on_answerable=1.0, min_correct_fallback_rate_on_unanswerable=0.0, max_p95_latency_ms=999999, max_regression_tolerance=1.0)
    verdict = evaluate_gate(summary, policy=lenient_policy, run_status="completed")
    assert verdict.passed is False
    assert any("hard failure" in reason for reason in verdict.reasons)


def test_gate_fails_when_run_did_not_complete() -> None:
    summary = summarise_results([_row()])
    verdict = evaluate_gate(summary, policy=DEFAULT_POLICY, run_status="failed")
    assert verdict.passed is False
    assert any("did not complete" in reason for reason in verdict.reasons)


def test_gate_fails_when_citation_coverage_below_minimum() -> None:
    summary = summarise_results([_row(answer_metrics={"answer_produced": True, "citation_present": False})])
    strict_policy = EvaluationPolicy(min_citation_coverage=0.9)
    verdict = evaluate_gate(summary, policy=strict_policy, run_status="completed")
    assert verdict.passed is False
    assert any("citation coverage" in reason for reason in verdict.reasons)


def test_gate_fails_when_latency_p95_exceeds_maximum() -> None:
    summary = summarise_results([_row(latency_ms=10000)])
    strict_policy = EvaluationPolicy(max_p95_latency_ms=5000)
    verdict = evaluate_gate(summary, policy=strict_policy, run_status="completed")
    assert verdict.passed is False
    assert any("latency" in reason for reason in verdict.reasons)


def test_gate_fails_on_regression_beyond_tolerance() -> None:
    baseline = summarise_results([_row(), _row(case_id="case-2"), _row(case_id="case-3"), _row(case_id="case-4")])
    candidate = summarise_results([_row(), _row(case_id="case-2", passed=False, failure_reasons=["x"]), _row(case_id="case-3", passed=False, failure_reasons=["y"]), _row(case_id="case-4")])
    strict_policy = EvaluationPolicy(max_regression_tolerance=0.1)
    verdict = evaluate_gate(candidate, policy=strict_policy, run_status="completed", baseline=baseline)
    assert verdict.passed is False
    assert any("dropped" in reason for reason in verdict.reasons)


def test_gate_allows_regression_within_tolerance() -> None:
    baseline = summarise_results([_row(), _row(case_id="case-2"), _row(case_id="case-3"), _row(case_id="case-4")])
    candidate = summarise_results([_row(), _row(case_id="case-2"), _row(case_id="case-3"), _row(case_id="case-4", passed=False, failure_reasons=["minor"])])
    lenient_policy = EvaluationPolicy(max_regression_tolerance=0.5)
    verdict = evaluate_gate(candidate, policy=lenient_policy, run_status="completed", baseline=baseline)
    assert verdict.passed is True
