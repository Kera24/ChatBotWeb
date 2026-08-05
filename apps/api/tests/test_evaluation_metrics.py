from app.evaluation.metrics.aggregate import compare_to_baseline, summarise_results
from app.evaluation.metrics.answer import compute_answer_metrics
from app.evaluation.metrics.retrieval import compute_retrieval_metrics
from app.evaluation.redaction import redact_secrets, safe_error_message
from app.evaluation.scoring import score_case


# --- retrieval metrics --------------------------------------------------------


def test_retrieval_metrics_hit_and_recall_when_expected_document_present() -> None:
    metrics = compute_retrieval_metrics(
        expected_document_ids=["doc-1"],
        expected_source_labels=None,
        retrieved_document_ids=["doc-2", "doc-1"],
        retrieved_chunk_ids=["chunk-2", "chunk-1"],
        retrieved_source_labels=["Doc Two", "Doc One"],
        allowed_document_ids=None,
    )
    assert metrics.hit_at_k is True
    assert metrics.expected_document_retrieved is True
    assert metrics.recall_at_k == 1.0
    assert metrics.precision_at_k == 0.5
    assert metrics.reciprocal_rank == 0.5  # doc-1 found at rank 2


def test_retrieval_metrics_miss_when_expected_document_absent() -> None:
    metrics = compute_retrieval_metrics(
        expected_document_ids=["doc-missing"],
        expected_source_labels=None,
        retrieved_document_ids=["doc-2"],
        retrieved_chunk_ids=["chunk-2"],
        retrieved_source_labels=["Doc Two"],
        allowed_document_ids=None,
    )
    assert metrics.hit_at_k is False
    assert metrics.expected_document_retrieved is False
    assert metrics.reciprocal_rank == 0.0


def test_retrieval_metrics_none_when_no_expectations_declared() -> None:
    metrics = compute_retrieval_metrics(
        expected_document_ids=None,
        expected_source_labels=None,
        retrieved_document_ids=["doc-1"],
        retrieved_chunk_ids=["chunk-1"],
        retrieved_source_labels=["Doc One"],
        allowed_document_ids=None,
    )
    assert metrics.hit_at_k is None
    assert metrics.expected_document_retrieved is None
    assert metrics.recall_at_k is None


def test_retrieval_metrics_detects_duplicate_chunks() -> None:
    metrics = compute_retrieval_metrics(
        expected_document_ids=None,
        expected_source_labels=None,
        retrieved_document_ids=["doc-1", "doc-1"],
        retrieved_chunk_ids=["chunk-1", "chunk-1"],
        retrieved_source_labels=["Doc One", "Doc One"],
        allowed_document_ids=None,
    )
    assert metrics.duplicate_context_rate == 0.5


def test_retrieval_metrics_flags_unauthorised_source() -> None:
    metrics = compute_retrieval_metrics(
        expected_document_ids=None,
        expected_source_labels=None,
        retrieved_document_ids=["foreign-doc"],
        retrieved_chunk_ids=["foreign-chunk"],
        retrieved_source_labels=["Foreign"],
        allowed_document_ids=["allowed-doc"],
    )
    assert metrics.cross_assistant_retrieval_failure is True
    assert metrics.unauthorised_source_failure is True


# --- answer metrics -----------------------------------------------------------


def test_answer_metrics_flags_unsafe_html() -> None:
    metrics = compute_answer_metrics(
        answer="Sure! <script>alert(1)</script>",
        answer_state="answered",
        expected_answerability="answerable",
        citation_document_ids=[],
        expected_source_labels=None,
        cited_source_labels=[],
        retrieved_document_ids=[],
        allowed_document_ids=None,
        latency_ms=100,
        total_tokens=50,
        max_latency_ms=8000,
        max_tokens=2000,
    )
    assert metrics.unsafe_html_present is True


def test_answer_metrics_flags_system_prompt_leak_pattern() -> None:
    metrics = compute_answer_metrics(
        answer="My system prompt says I must always cite sources.",
        answer_state="answered",
        expected_answerability="answerable",
        citation_document_ids=[],
        expected_source_labels=None,
        cited_source_labels=[],
        retrieved_document_ids=[],
        allowed_document_ids=None,
        latency_ms=100,
        total_tokens=50,
        max_latency_ms=8000,
        max_tokens=2000,
    )
    assert metrics.system_prompt_leak_detected is True


def test_answer_metrics_flags_secret_exposure() -> None:
    metrics = compute_answer_metrics(
        answer="Connect using postgresql://user:pass@host:5432/db",
        answer_state="answered",
        expected_answerability="answerable",
        citation_document_ids=[],
        expected_source_labels=None,
        cited_source_labels=[],
        retrieved_document_ids=[],
        allowed_document_ids=None,
        latency_ms=100,
        total_tokens=50,
        max_latency_ms=8000,
        max_tokens=2000,
    )
    assert metrics.secret_exposure_detected is True


def test_answer_metrics_expected_fallback_matched_for_unanswerable_case() -> None:
    metrics = compute_answer_metrics(
        answer="I do not have information about that.",
        answer_state="fallback",
        expected_answerability="unanswerable",
        citation_document_ids=[],
        expected_source_labels=None,
        cited_source_labels=[],
        retrieved_document_ids=[],
        allowed_document_ids=None,
        latency_ms=100,
        total_tokens=None,
        max_latency_ms=8000,
        max_tokens=2000,
    )
    assert metrics.expected_fallback_matched is True


def test_answer_metrics_flags_unexpected_answer_on_unanswerable_case() -> None:
    metrics = compute_answer_metrics(
        answer="The deadline is March 1st.",
        answer_state="answered",
        expected_answerability="unanswerable",
        citation_document_ids=["doc-1"],
        expected_source_labels=None,
        cited_source_labels=["Doc"],
        retrieved_document_ids=["doc-1"],
        allowed_document_ids=None,
        latency_ms=100,
        total_tokens=50,
        max_latency_ms=8000,
        max_tokens=2000,
    )
    assert metrics.expected_fallback_matched is False


def test_answer_metrics_flags_unsupported_citation_identifier() -> None:
    metrics = compute_answer_metrics(
        answer="Here is the answer.",
        answer_state="answered",
        expected_answerability="answerable",
        citation_document_ids=["doc-not-retrieved"],
        expected_source_labels=None,
        cited_source_labels=["Doc"],
        retrieved_document_ids=["doc-actually-retrieved"],
        allowed_document_ids=None,
        latency_ms=100,
        total_tokens=50,
        max_latency_ms=8000,
        max_tokens=2000,
    )
    assert metrics.unsupported_citation_identifier is True


def test_answer_metrics_latency_and_token_thresholds() -> None:
    metrics = compute_answer_metrics(
        answer="Answer.",
        answer_state="answered",
        expected_answerability="answerable",
        citation_document_ids=[],
        expected_source_labels=None,
        cited_source_labels=[],
        retrieved_document_ids=[],
        allowed_document_ids=None,
        latency_ms=9000,
        total_tokens=3000,
        max_latency_ms=8000,
        max_tokens=2000,
    )
    assert metrics.latency_threshold_ok is False
    assert metrics.token_threshold_ok is False


# --- scoring --------------------------------------------------------------


def test_score_case_hard_fails_on_cross_tenant_leak() -> None:
    retrieval = compute_retrieval_metrics(
        expected_document_ids=None, expected_source_labels=None,
        retrieved_document_ids=[], retrieved_chunk_ids=[], retrieved_source_labels=[], allowed_document_ids=None,
    )
    answer = compute_answer_metrics(
        answer="Here is the foreign tenant's data.", answer_state="answered", expected_answerability="unanswerable",
        citation_document_ids=[], expected_source_labels=None, cited_source_labels=[], retrieved_document_ids=[],
        allowed_document_ids=None, latency_ms=100, total_tokens=50, max_latency_ms=8000, max_tokens=2000,
        cross_tenant_leak_detected=True,
    )
    result = score_case(category="cross_assistant_leakage", expected_answerability="unanswerable", has_expected_documents=False, has_expected_sources=False, retrieval=retrieval, answer=answer)
    assert result.passed is False
    assert result.hard_failure is True
    assert "cross_tenant_leakage" in result.failure_reasons


def test_score_case_hard_fails_when_answer_given_instead_of_fallback() -> None:
    retrieval = compute_retrieval_metrics(
        expected_document_ids=None, expected_source_labels=None,
        retrieved_document_ids=["doc-1"], retrieved_chunk_ids=["chunk-1"], retrieved_source_labels=["Doc"], allowed_document_ids=None,
    )
    answer = compute_answer_metrics(
        answer="Confidently incorrect answer.", answer_state="answered", expected_answerability="unanswerable",
        citation_document_ids=["doc-1"], expected_source_labels=None, cited_source_labels=["Doc"], retrieved_document_ids=["doc-1"],
        allowed_document_ids=None, latency_ms=100, total_tokens=50, max_latency_ms=8000, max_tokens=2000,
    )
    result = score_case(category="unanswerable", expected_answerability="unanswerable", has_expected_documents=False, has_expected_sources=False, retrieval=retrieval, answer=answer)
    assert result.hard_failure is True
    assert "answer_returned_when_fallback_required" in result.failure_reasons


def test_score_case_passes_clean_answerable_case() -> None:
    retrieval = compute_retrieval_metrics(
        expected_document_ids=["doc-1"], expected_source_labels=None,
        retrieved_document_ids=["doc-1"], retrieved_chunk_ids=["chunk-1"], retrieved_source_labels=["Doc"], allowed_document_ids=["doc-1"],
    )
    answer = compute_answer_metrics(
        answer="The deadline is March 1st. [1]", answer_state="answered", expected_answerability="answerable",
        citation_document_ids=["doc-1"], expected_source_labels=None, cited_source_labels=["Doc"], retrieved_document_ids=["doc-1"],
        allowed_document_ids=["doc-1"], latency_ms=100, total_tokens=50, max_latency_ms=8000, max_tokens=2000,
    )
    result = score_case(category="answerable_factual", expected_answerability="answerable", has_expected_documents=True, has_expected_sources=False, retrieval=retrieval, answer=answer)
    assert result.passed is True
    assert result.hard_failure is False
    assert result.failure_reasons == []


def test_score_case_soft_fails_when_citation_required_but_missing() -> None:
    retrieval = compute_retrieval_metrics(
        expected_document_ids=None, expected_source_labels=None,
        retrieved_document_ids=[], retrieved_chunk_ids=[], retrieved_source_labels=[], allowed_document_ids=None,
    )
    answer = compute_answer_metrics(
        answer="Sure, the deadline is March 1st.", answer_state="answered", expected_answerability="answerable",
        citation_document_ids=[], expected_source_labels=None, cited_source_labels=[], retrieved_document_ids=[],
        allowed_document_ids=None, latency_ms=100, total_tokens=50, max_latency_ms=8000, max_tokens=2000,
    )
    result = score_case(category="citation_required", expected_answerability="answerable", has_expected_documents=False, has_expected_sources=False, retrieval=retrieval, answer=answer)
    assert result.passed is False
    assert result.hard_failure is False
    assert "citation_required_but_missing" in result.failure_reasons


def test_score_case_honours_metadata_citation_required_flag_independent_of_category() -> None:
    """A case tagged citation_required=true in metadata_json should be scored
    for missing citations even when its category is not literally
    'citation_required' (e.g. an answerable_factual case that also demands a
    citation) - see app.evaluation.fixtures.golden_dataset.json."""
    retrieval = compute_retrieval_metrics(
        expected_document_ids=None, expected_source_labels=None,
        retrieved_document_ids=[], retrieved_chunk_ids=[], retrieved_source_labels=[], allowed_document_ids=None,
    )
    answer = compute_answer_metrics(
        answer="Sure, the deadline is March 1st.", answer_state="answered", expected_answerability="answerable",
        citation_document_ids=[], expected_source_labels=None, cited_source_labels=[], retrieved_document_ids=[],
        allowed_document_ids=None, latency_ms=100, total_tokens=50, max_latency_ms=8000, max_tokens=2000,
    )
    without_flag = score_case(category="answerable_factual", expected_answerability="answerable", has_expected_documents=False, has_expected_sources=False, retrieval=retrieval, answer=answer)
    assert without_flag.passed is True

    with_flag = score_case(category="answerable_factual", expected_answerability="answerable", has_expected_documents=False, has_expected_sources=False, retrieval=retrieval, answer=answer, citation_required=True)
    assert with_flag.passed is False
    assert "citation_required_but_missing" in with_flag.failure_reasons


# --- redaction --------------------------------------------------------------


def test_redact_secrets_strips_connection_strings_and_api_keys() -> None:
    text = "Failed to connect: postgresql://user:secret@db.internal:5432/app and key sk-abcdefghijklmnopqrstuvwx"
    redacted = redact_secrets(text)
    assert "postgresql://" not in redacted
    assert "sk-abcdefghijklmnopqrstuvwx" not in redacted
    assert "[REDACTED]" in redacted


def test_safe_error_message_truncates_and_redacts() -> None:
    class FakeError(Exception):
        pass

    message = safe_error_message(FakeError("connection failed: postgresql://user:pass@host/db " + "x" * 600))
    assert "postgresql://" not in message
    assert len(message) <= 520


# --- aggregation ------------------------------------------------------------


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


def test_summarise_results_computes_pass_rate_and_latency_percentiles() -> None:
    rows = [_row(latency_ms=100), _row(latency_ms=200), _row(case_id="case-2", passed=False, hard_failure=True, latency_ms=300, failure_reasons=["cross_tenant_leakage"])]
    summary = summarise_results(rows)
    assert summary.total_cases == 3
    assert summary.passed_cases == 2
    assert summary.hard_failure_cases == 1
    assert summary.pass_rate == 2 / 3
    assert summary.latency_p50_ms == 200
    assert summary.category_breakdown["answerable_factual"]["total"] == 3


def test_summarise_results_lists_only_failed_cases() -> None:
    rows = [_row(), _row(case_id="case-2", passed=False, failure_reasons=["expected_document_not_retrieved"])]
    summary = summarise_results(rows)
    assert len(summary.failed_cases_list) == 1
    assert summary.failed_cases_list[0].case_id == "case-2"


def test_compare_to_baseline_detects_regression() -> None:
    baseline_rows = [_row(), _row(case_id="case-2")]
    candidate_rows = [_row(), _row(case_id="case-2", passed=False, failure_reasons=["x"])]
    baseline = summarise_results(baseline_rows)
    candidate = summarise_results(candidate_rows)
    comparison = compare_to_baseline(candidate, baseline)
    assert comparison["regressed"] is True
    assert comparison["pass_rate_delta"] < 0
