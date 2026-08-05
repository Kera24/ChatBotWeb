from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.categories import ANSWERABILITY_VALUES, CASE_CATEGORY_VALUES, ISOLATION_CATEGORIES
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import load_golden_fixture_definition, seed_golden_dataset
from app.services.embeddings import build_embedding_provider


def test_golden_dataset_definition_is_well_formed() -> None:
    fixture = load_golden_fixture_definition()

    document_keys = {doc["key"] for doc in fixture["documents"]}
    assert len(document_keys) == len(fixture["documents"]), "document keys must be unique"

    cases = fixture["cases"]
    assert 60 <= len(cases) <= 100, "golden dataset must have 60-100 cases per the task specification"

    questions = [case["question"] for case in cases]
    non_empty_questions = [q for q in questions if q]
    assert len(non_empty_questions) == len(set(non_empty_questions)), "no two non-empty-string questions should be identical"

    for case in cases:
        assert case["category"] in CASE_CATEGORY_VALUES, f"unknown category {case['category']!r}"
        assert case["expected_answerability"] in ANSWERABILITY_VALUES, f"unknown answerability {case['expected_answerability']!r}"
        for key in case.get("expected_document_keys", []):
            assert key in document_keys, f"case references unknown document key {key!r}"

    isolation_case_count = sum(1 for case in cases if case["category"] in {member.value for member in ISOLATION_CATEGORIES})
    assert isolation_case_count > 0
    for case in cases:
        if case["category"] in {member.value for member in ISOLATION_CATEGORIES}:
            assert "cross_tenant_attempt" in case, f"isolation case must declare cross_tenant_attempt: {case['question']!r}"


def test_golden_dataset_covers_every_declared_category() -> None:
    fixture = load_golden_fixture_definition()
    categories_present = {case["category"] for case in fixture["cases"]}
    # Every category defined in the closed vocabulary should have at least one
    # authored case, so the category-breakdown report is never silently empty
    # for a whole category.
    assert categories_present == CASE_CATEGORY_VALUES


@pytest.fixture()
def db_session():
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "golden-fixture-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)

    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db: Session) -> tuple[Organisation, Workspace, str]:
    organisation = Organisation(name="Golden Fixture Org", slug="golden-fixture-org", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug="golden-fixture-workspace", status="active", default_language="en")
    user = User(email="owner@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation, workspace, user.id


def test_seed_golden_dataset_creates_documents_widget_and_cases(db_session: Session) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session)
    embedding_provider = build_embedding_provider(provider_name="local-mock", model_name="golden-fixture-test", dimension=8)

    fixture = load_golden_fixture_definition()
    loaded = seed_golden_dataset(db_session, organisation=organisation, workspace=workspace, embedding_provider=embedding_provider, actor_user_id=user_id)

    assert len(loaded.document_ids) == len(fixture["documents"])
    assert loaded.dataset.name == fixture["dataset"]["name"]
    assert len(fixture["cases"]) > 0


def test_running_the_same_golden_case_twice_in_mock_mode_is_deterministic(db_session: Session) -> None:
    """Mock-mode runs must be fully reproducible: rerunning the identical
    dataset/case set produces identical pass/fail results and metrics, which
    is the basis for trusting a baseline-vs-candidate comparison at all."""
    organisation, workspace, user_id = _seed_tenant(db_session)
    embedding_provider = build_embedding_provider(provider_name="local-mock", model_name="golden-fixture-test", dimension=8)
    loaded = seed_golden_dataset(db_session, organisation=organisation, workspace=workspace, embedding_provider=embedding_provider, actor_user_id=user_id)

    options = EvaluationRunOptions(mode="mock", category_filter="answerable_factual")
    first_run = run_evaluation(db_session, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id, options=options)
    second_run = run_evaluation(db_session, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id, options=options)

    assert first_run.total_cases == second_run.total_cases
    assert first_run.passed_cases == second_run.passed_cases
    assert first_run.failed_cases == second_run.failed_cases
    assert first_run.hard_failure_cases == second_run.hard_failure_cases


def test_category_filter_restricts_run_to_matching_cases(db_session: Session) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session)
    embedding_provider = build_embedding_provider(provider_name="local-mock", model_name="golden-fixture-test", dimension=8)
    fixture = load_golden_fixture_definition()
    loaded = seed_golden_dataset(db_session, organisation=organisation, workspace=workspace, embedding_provider=embedding_provider, actor_user_id=user_id)

    expected_count = sum(1 for case in fixture["cases"] if case["category"] == "prompt_injection")
    run = run_evaluation(
        db_session, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id,
        options=EvaluationRunOptions(mode="mock", category_filter="prompt_injection"),
    )
    assert run.total_cases == expected_count
