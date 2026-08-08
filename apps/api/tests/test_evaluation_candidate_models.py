from __future__ import annotations

from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import EvaluationCandidate, EvaluationDataset, EvaluationDatasetVersionEvent, EvaluationRegressionReport, Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app
from app.repositories import evaluation_candidate_repository, evaluation_repository


def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_0018_creates_and_drops_feedback_loop_tables(tmp_path) -> None:
    database_path = tmp_path / "feedback-loop-migration.db"
    database_url = f"sqlite:///{database_path}"
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert {"evaluation_candidates", "evaluation_dataset_version_events", "evaluation_regression_reports"} <= tables
    columns = {column["name"] for column in inspect(engine).get_columns("evaluation_cases")}
    assert "source_candidate_id" in columns
    run_columns = {column["name"] for column in inspect(engine).get_columns("evaluation_runs")}
    assert "trigger_source" in run_columns
    engine.dispose()

    command.downgrade(config, "0017_ai_observability")
    engine = create_engine(database_url)
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert not ({"evaluation_candidates", "evaluation_dataset_version_events", "evaluation_regression_reports"} & tables_after_downgrade)
    columns_after_downgrade = {column["name"] for column in inspect(engine).get_columns("evaluation_cases")}
    assert "source_candidate_id" not in columns_after_downgrade
    engine.dispose()


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def seed_tenant(client: TestClient, *, slug: str) -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active")
        user = User(email=f"owner-{unique}@example.test")
        workspace = Workspace(organisation=org, name="Workspace", slug=f"{slug}-workspace-{unique}", status="active")
        membership = Membership(organisation=org, user=user, role="org_owner", status="active")
        db.add_all([org, user, workspace, membership])
        db.commit()
        widget = create_widget(
            db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id
        )
        return org.id, workspace.id, widget.id


def test_candidate_crud_round_trip(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="candidates")
    with client.app.state.testing_session() as db:
        candidate = evaluation_candidate_repository.create_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="fallback",
            severity="medium",
            question="How do I reset my password?",
            response=None,
            reason_code="fallback",
        )
        assert candidate.id is not None
        assert candidate.triage_status == "new"
        assert candidate.occurrence_count == 1

        fetched = evaluation_candidate_repository.get_candidate(db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate.id)
        assert fetched is not None
        assert fetched.redacted_question == "How do I reset my password?"


def test_dataset_version_event_and_regression_report_persist(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="versioning")
    with client.app.state.testing_session() as db:
        dataset = evaluation_repository.create_dataset(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, name="Golden", description=None, version="1", created_by=None
        )
        case = evaluation_repository.create_case(
            db,
            dataset=dataset,
            question="q",
            reference_answer="a",
            expected_document_ids=None,
            expected_source_labels=None,
            expected_answerability="answerable",
            category="answerable_factual",
            tags=None,
            metadata_json=None,
        )
        event = EvaluationDatasetVersionEvent(
            dataset_id=dataset.id,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            from_version="1",
            to_version="2",
            case_id=case.id,
            candidate_id=None,
            created_by=None,
            changelog_note="manual test bump",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.id is not None

        report = evaluation_candidate_repository.create_regression_report(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            dataset_id=dataset.id,
            run_id=str(uuid4()),
            baseline_run_id=None,
            report={"new_cases": []},
            verdict_passed=True,
            verdict_reasons=[],
            created_by="system:test",
        )
        assert report.id is not None
        assert report.verdict_passed is True

        fetched_events = evaluation_candidate_repository.list_dataset_version_events(db, organisation_id=organisation_id, workspace_id=workspace_id)
        assert len(fetched_events) == 1
        fetched_reports = evaluation_candidate_repository.list_regression_reports(db, organisation_id=organisation_id, workspace_id=workspace_id)
        assert len(fetched_reports) == 1
