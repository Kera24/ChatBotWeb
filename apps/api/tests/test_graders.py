"""Tests for app.evaluation.graders - the optional LLM-based grader system
(Section 15 of the grader task). Covers the provider abstraction in
isolation (no DB) and the engine's DB-integrated grading/persistence/
consistency/caching behaviour against a real seeded evaluation run.

Live Ollama grader tests are intentionally not included here - they require
a locally running model and are exercised manually per
docs/04_Engineering/Grader_Architecture.md's "local Ollama grader setup"
section, not as part of the standard `pytest`/`npm run api:test` suite.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import (
    Chunk,
    Document,
    DocumentVersion,
    EvaluationCase,
    EvaluationDataset,
    Membership,
    Organisation,
    User,
    Workspace,
)
from app.evaluation.categories import Answerability, CaseCategory
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.graders.cache import GraderResultCache, cache_key
from app.evaluation.graders.calibration import run_calibration
from app.evaluation.graders.claims import extract_claims, deterministic_value_support
from app.evaluation.graders.config import build_mock_grader_provider, build_real_eval_grader_provider, load_eval_grader_config_from_env
from app.evaluation.graders.context import EvidenceItem, GradingContext
from app.evaluation.graders.contracts import GraderResult, PairwiseVerdict
from app.evaluation.graders.engine import (
    GradingRunStats,
    build_grading_context,
    compare_pairwise_with_swap_check,
    grade_one_dimension,
    grade_result,
)
from app.evaluation.graders.errors import GraderNotConfiguredError
from app.evaluation.graders.grading_report import build_grading_summary
from app.evaluation.graders.provider import MockGraderProvider
from app.evaluation.graders.rubrics import RUBRICS, GraderDimension, get_rubric
from app.operations import eval_grade
from app.repositories import evaluation_repository


# --- provider abstraction / config -----------------------------------------

def test_mock_provider_returns_structured_result() -> None:
    provider = build_mock_grader_provider()
    context = GradingContext(
        question="How much does the Team plan cost?", answer="The Team plan costs $29 per month. [1]",
        answer_state="answered", category="answerable_factual", expected_answerability="answerable", reference_answer=None,
        evidence=(EvidenceItem(evidence_id="1", chunk_id="c1", document_title="Pricing Plans", content="Team costs $29 per month."),),
    )
    result = provider.grade(rubric=get_rubric(GraderDimension.GROUNDEDNESS), context=context)
    assert isinstance(result, GraderResult)
    assert result.dimension == GraderDimension.GROUNDEDNESS
    assert result.grader_provider == "mock"
    assert result.is_model_generated_estimate is True


def test_unavailable_grader_raises_clear_error_not_silent_fallback() -> None:
    with pytest.raises(GraderNotConfiguredError):
        build_real_eval_grader_provider()


def test_ollama_grader_requires_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_GRADER_PROVIDER", "ollama")
    monkeypatch.delenv("EVAL_GRADER_MODEL", raising=False)
    with pytest.raises(GraderNotConfiguredError):
        build_real_eval_grader_provider(load_eval_grader_config_from_env())


def test_unknown_provider_raises() -> None:
    from app.evaluation.graders.config import EvalGraderConfig
    with pytest.raises(GraderNotConfiguredError):
        build_real_eval_grader_provider(EvalGraderConfig(provider="nonexistent", model="x", base_url="http://x", temperature=0.0, max_tokens=10, timeout_seconds=5.0))


# --- structured output validation ------------------------------------------

def test_grader_result_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        GraderResult(dimension=GraderDimension.RELEVANCE, score=1.5, passed=True, confidence=0.5, reason="x", prompt_version="v1", grader_provider="mock", grader_model="m")


def test_grader_result_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        GraderResult(dimension=GraderDimension.RELEVANCE, score=0.5, passed=True, confidence=0.5, reason="   ", prompt_version="v1", grader_provider="mock", grader_model="m")


def test_pairwise_verdict_rejects_invalid_verdict_value() -> None:
    with pytest.raises(ValidationError):
        PairwiseVerdict(verdict="a_is_way_better", reason="x", rubric_dimension="relevance", grader_provider="mock", grader_model="m", prompt_version="v1")


def test_malformed_ollama_output_raises_validation_error() -> None:
    from app.evaluation.graders.errors import GraderOutputValidationError
    from app.evaluation.graders.ollama_provider import OllamaGraderProvider

    provider = OllamaGraderProvider(model_name="test-model")
    provider._call = lambda **kwargs: "not valid json at all {{{"
    with pytest.raises(GraderOutputValidationError):
        provider.grade(rubric=get_rubric(GraderDimension.RELEVANCE), context=GradingContext(question="q", answer="a", answer_state="answered", category="answerable_factual", expected_answerability="answerable", reference_answer=None))


def test_malformed_ollama_output_missing_required_field_raises() -> None:
    from app.evaluation.graders.errors import GraderOutputValidationError
    from app.evaluation.graders.ollama_provider import OllamaGraderProvider

    provider = OllamaGraderProvider(model_name="test-model")
    provider._call = lambda **kwargs: '{"score": 2.0}'  # score out of range, no reason
    with pytest.raises(GraderOutputValidationError):
        provider.grade(rubric=get_rubric(GraderDimension.RELEVANCE), context=GradingContext(question="q", answer="a", answer_state="answered", category="answerable_factual", expected_answerability="answerable", reference_answer=None))


# --- every rubric dimension exists and is well-formed -----------------------

@pytest.mark.parametrize("dimension", list(GraderDimension))
def test_every_dimension_has_a_complete_rubric(dimension: GraderDimension) -> None:
    rubric = get_rubric(dimension)
    assert rubric.rubric
    assert 0.0 <= rubric.pass_threshold <= 1.0
    assert rubric.score_range == (0.0, 1.0)
    assert rubric.strong_example and rubric.weak_example and rubric.invalid_example
    assert rubric.limitations
    assert isinstance(rubric.gating, bool)


def test_no_dimension_is_gating_at_introduction() -> None:
    # Section 12: "groundedness and citation-support graders may become
    # gating only after successful human calibration" - not yet approved.
    assert all(not rubric.gating for rubric in RUBRICS.values())


# --- claim-level grading -----------------------------------------------------

def test_claim_extraction_splits_sentences_and_citations() -> None:
    claims = extract_claims("The Team plan costs $29 per month. [1] It includes 1TB of storage. [1]")
    assert len(claims) >= 2
    assert claims[0].currency_values


def test_deterministic_value_support_detects_unsupported_claim() -> None:
    claims = extract_claims("Refunds are available within 30 days.")
    supported = deterministic_value_support(claims[0], "Monthly customers get a 14-day money-back guarantee.")
    assert supported is False


def test_deterministic_value_support_detects_supported_claim() -> None:
    claims = extract_claims("The plan costs $29 per month.")
    supported = deterministic_value_support(claims[0], "Team costs $29 per month and includes storage.")
    assert supported is True


def test_deterministic_value_support_none_when_no_checkable_values() -> None:
    claims = extract_claims("This plan is a great choice for growing teams.")
    assert deterministic_value_support(claims[0], "anything") is None


# --- pairwise comparison + order swap ---------------------------------------

def test_pairwise_comparison_returns_a_verdict() -> None:
    provider = build_mock_grader_provider()
    verdict = provider.compare_pairwise(
        rubric=get_rubric(GraderDimension.GROUNDEDNESS), question="How much does Team cost?",
        answer_a="Team costs $29 per month.", answer_b="I have no idea.", evidence_block="Team costs $29 per month.",
    )
    assert verdict.verdict in ("a_better", "b_better", "tie", "both_unacceptable")


def test_pairwise_swap_check_is_order_independent_for_mock_provider() -> None:
    provider = build_mock_grader_provider()
    forward, swapped, consistent = compare_pairwise_with_swap_check(
        provider=provider, rubric=get_rubric(GraderDimension.GROUNDEDNESS), question="How much does Team cost?",
        answer_baseline="Team costs $29 per month.", answer_candidate="I have no idea.", evidence_block="Team costs $29 per month.",
    )
    assert forward.order_swapped is False
    assert swapped.order_swapped is True
    assert consistent is True  # the mock heuristic is a pure function of content, not position, so no bias


# --- consistency measurement -------------------------------------------------

def test_repeated_grading_reports_perfect_consistency_for_deterministic_mock() -> None:
    provider = build_mock_grader_provider()
    context = GradingContext(question="q", answer="Team costs $29.", answer_state="answered", category="answerable_factual", expected_answerability="answerable", reference_answer=None, evidence=(EvidenceItem(evidence_id="1", chunk_id="c1", document_title="Pricing", content="Team costs $29."),))
    outcome = grade_one_dimension(provider=provider, rubric=get_rubric(GraderDimension.GROUNDEDNESS), context=context, repetitions=3)
    assert outcome.consistency is not None
    assert outcome.consistency.repetitions == 3
    assert outcome.consistency.agreement_rate == 1.0
    assert outcome.consistency.score_variance == 0.0
    assert outcome.consistency.is_consistent is True


# --- caching ------------------------------------------------------------------

def test_cache_hit_on_second_identical_call() -> None:
    provider = build_mock_grader_provider()
    cache = GraderResultCache()
    context = GradingContext(question="q", answer="a", answer_state="answered", category="answerable_factual", expected_answerability="answerable", reference_answer=None)
    rubric = get_rubric(GraderDimension.RELEVANCE)
    grade_one_dimension(provider=provider, rubric=rubric, context=context, cache=cache)
    outcome_2 = grade_one_dimension(provider=provider, rubric=rubric, context=context, cache=cache)
    assert outcome_2.from_cache is True
    assert cache.stats()["hits"] == 1


def test_cache_key_differs_for_different_answers() -> None:
    ctx1 = GradingContext(question="q", answer="a", answer_state="answered", category="answerable_factual", expected_answerability="answerable", reference_answer=None)
    ctx2 = GradingContext(question="q", answer="different answer", answer_state="answered", category="answerable_factual", expected_answerability="answerable", reference_answer=None)
    key1 = cache_key(dimension=GraderDimension.RELEVANCE, context=ctx1, rubric_version="v1", grader_model="mock-grader-v1")
    key2 = cache_key(dimension=GraderDimension.RELEVANCE, context=ctx2, rubric_version="v1", grader_model="mock-grader-v1")
    assert key1 != key2


# --- calibration reporting ---------------------------------------------------

def test_calibration_runs_against_all_examples() -> None:
    provider = build_mock_grader_provider()
    report = run_calibration(provider=provider)
    assert report.total_examples >= 10
    assert set(report.per_dimension) <= {d.value for d in GraderDimension}


def test_calibration_agreement_rate_is_between_zero_and_one() -> None:
    provider = build_mock_grader_provider()
    report = run_calibration(provider=provider)
    for dim in report.per_dimension:
        rate = report.agreement_rate(dim)
        assert rate is None or 0.0 <= rate <= 1.0


def test_calibration_gating_threshold_not_met_marks_dimension_not_gating_ready() -> None:
    provider = build_mock_grader_provider()
    report = run_calibration(provider=provider)
    # The mock heuristic is intentionally crude for fallback_appropriateness/clarification_quality
    # (documented in Grader_Architecture.md) - confirm the calibration mechanism correctly
    # identifies this rather than rubber-stamping every dimension as gating-ready.
    assert any(not report.meets_gating_threshold(dim) for dim in report.per_dimension)


# --- DB-integrated: engine + persistence + isolation/redaction --------------

@pytest.fixture()
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'graders.db'}"


@pytest.fixture()
def db_session(db_url: str):
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "grader-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db: Session, *, suffix: str) -> tuple[Organisation, Workspace, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation, workspace, user.id


def _seed_document(db: Session, *, organisation_id: str, workspace_id: str, key: str, title: str, content: str) -> str:
    document = Document(organisation_id=organisation_id, workspace_id=workspace_id, title=title, source_type="txt", source_key=f"{key}.txt", status="ready")
    db.add(document)
    db.flush()
    version = DocumentVersion(organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, version_number=1, checksum=f"checksum-{key}", processing_status="ready")
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    chunk = Chunk(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()), source_type="txt",
        source_title=title, status="ready", embedding_provider="local-mock", embedding_model="grader-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    )
    db.add(chunk)
    db.commit()
    return document.id


def _seed_run(db: Session, *, db_url: str) -> tuple[str, str, str, str]:
    organisation, workspace, user_id = _seed_tenant(db, suffix="graders")
    # Question/content pairing reused verbatim from tests/test_evaluation_engine.py,
    # which is already known to retrieve and answer successfully under the
    # local-mock (hash-based, non-semantic) embedding provider - an arbitrary
    # question/content pairing is not guaranteed to score above the retrieval
    # similarity threshold since local-mock similarity is not meaningful.
    document_id = _seed_document(db, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Grader test dataset", version="1", status="active")
    db.add(dataset)
    db.flush()
    db.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="When do applications close?", expected_document_ids=[document_id],
        expected_answerability=Answerability.ANSWERABLE.value, category=CaseCategory.ANSWERABLE_FACTUAL.value,
    ))
    db.commit()
    db.refresh(dataset)

    run = run_evaluation(db, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url))
    return organisation.id, workspace.id, widget.id, run.id


def test_grade_result_persists_to_judge_scores_json(db_session: Session, db_url: str) -> None:
    _, _, _, run_id = _seed_run(db_session, db_url=db_url)
    results = evaluation_repository.list_results_for_run(db_session, run_id=run_id)
    result = results[0]
    case = db_session.get(EvaluationCase, result.case_id)
    provider = build_mock_grader_provider()

    grade_result(db_session, result=result, case=case, provider=provider, dimensions=(GraderDimension.RELEVANCE, GraderDimension.GROUNDEDNESS))
    db_session.refresh(result)

    assert result.judge_scores_json is not None
    assert result.judge_scores_json["grader_provider"] == "mock"
    assert "relevance" in result.judge_scores_json["dimensions"]
    assert "groundedness" in result.judge_scores_json["dimensions"]


def test_grading_does_not_alter_deterministic_fields(db_session: Session, db_url: str) -> None:
    _, _, _, run_id = _seed_run(db_session, db_url=db_url)
    results = evaluation_repository.list_results_for_run(db_session, run_id=run_id)
    result = results[0]
    case = db_session.get(EvaluationCase, result.case_id)
    passed_before, hard_failure_before, answer_before = result.passed, result.hard_failure, result.actual_answer

    grade_result(db_session, result=result, case=case, provider=build_mock_grader_provider(), dimensions=tuple(GraderDimension))
    db_session.refresh(result)

    assert result.passed == passed_before
    assert result.hard_failure == hard_failure_before
    assert result.actual_answer == answer_before


def test_regrading_a_subset_merges_not_overwrites(db_session: Session, db_url: str) -> None:
    _, _, _, run_id = _seed_run(db_session, db_url=db_url)
    results = evaluation_repository.list_results_for_run(db_session, run_id=run_id)
    result = results[0]
    case = db_session.get(EvaluationCase, result.case_id)
    provider = build_mock_grader_provider()

    grade_result(db_session, result=result, case=case, provider=provider, dimensions=tuple(GraderDimension))
    db_session.refresh(result)
    all_dims_after_first = set(result.judge_scores_json["dimensions"])
    assert len(all_dims_after_first) > 1

    grade_result(db_session, result=result, case=case, provider=provider, dimensions=(GraderDimension.GROUNDEDNESS,))
    db_session.refresh(result)
    assert set(result.judge_scores_json["dimensions"]) == all_dims_after_first


def test_grading_context_excludes_unauthorised_evidence(db_session: Session, db_url: str) -> None:
    _, _, _, run_id = _seed_run(db_session, db_url=db_url)
    results = evaluation_repository.list_results_for_run(db_session, run_id=run_id)
    result = results[0]
    case = db_session.get(EvaluationCase, result.case_id)
    context = build_grading_context(db_session, result=result, case=case)
    # Every evidence item must trace back to an actual citation the assistant made - never a fabricated/unscoped fetch.
    cited_chunk_ids = {c.get("chunk_id") for c in (result.citations_json or [])}
    for item in context.evidence:
        assert item.chunk_id in cited_chunk_ids


def test_grading_context_redacts_secrets_in_answer(db_session: Session, db_url: str) -> None:
    _, _, _, run_id = _seed_run(db_session, db_url=db_url)
    results = evaluation_repository.list_results_for_run(db_session, run_id=run_id)
    result = results[0]
    result.actual_answer = "Here is a key: sk-abcdefghijklmnopqrstuvwx and connection postgres://user:pass@host/db"
    db_session.commit()
    case = db_session.get(EvaluationCase, result.case_id)
    context = build_grading_context(db_session, result=result, case=case)
    assert "sk-abcdefghijklmnopqrstuvwx" not in context.answer
    assert "postgres://user:pass@host/db" not in context.answer


def test_grading_summary_and_disagreement_report(db_session: Session, db_url: str) -> None:
    _, _, _, run_id = _seed_run(db_session, db_url=db_url)
    results = evaluation_repository.list_results_for_run(db_session, run_id=run_id)
    result = results[0]
    case = db_session.get(EvaluationCase, result.case_id)
    grade_result(db_session, result=result, case=case, provider=build_mock_grader_provider(), dimensions=tuple(GraderDimension))

    summary = build_grading_summary(db_session, run_id=run_id)
    assert summary.graded_result_count >= 1
    assert "groundedness" in summary.dimensions
    payload = summary.as_dict()
    assert "disclaimer" in payload
    assert "model-generated estimates" in payload["disclaimer"]


# --- CLI exit behaviour -------------------------------------------------------

def test_eval_grade_calibrate_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = eval_grade.main(["--calibrate", "--format", "json"])
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "total_examples" in captured


def test_eval_grade_missing_run_args_exits_2() -> None:
    assert eval_grade.main([]) == 2


def test_eval_grade_run_not_found_exits_2(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(eval_grade, "SessionLocal", sessionmaker(bind=engine))
    assert eval_grade.main(["--run", "does-not-exist", "--organisation", "org", "--workspace", "ws"]) == 2


def test_eval_grade_real_provider_unconfigured_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVAL_GRADER_PROVIDER", raising=False)
    monkeypatch.setenv("EVAL_GRADER_PROVIDER", "ollama")
    monkeypatch.delenv("EVAL_GRADER_MODEL", raising=False)
    assert eval_grade.main(["--run", "x", "--organisation", "org", "--workspace", "ws"]) == 2
