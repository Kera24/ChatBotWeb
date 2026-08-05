from __future__ import annotations

from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import EvaluationCase, EvaluationDataset, EvaluationResult, EvaluationRun, Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app


def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_0016_creates_and_drops_evaluation_tables(tmp_path) -> None:
    database_path = tmp_path / "eval-migration.db"
    database_url = f"sqlite:///{database_path}"
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert {"evaluation_datasets", "evaluation_cases", "evaluation_runs", "evaluation_results"} <= tables
    engine.dispose()

    command.downgrade(config, "0015_billing_foundation")
    engine = create_engine(database_url)
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert not ({"evaluation_datasets", "evaluation_cases", "evaluation_runs", "evaluation_results"} & tables_after_downgrade)
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
        return org.id, workspace.id, user.id


def test_evaluation_dataset_and_case_crud_round_trip(client: TestClient) -> None:
    org_id, workspace_id, user_id = seed_tenant(client, slug="crud")
    with client.app.state.testing_session() as db:
        from app.access.widget_admin.service import create_widget

        widget = create_widget(db, organisation_id=org_id, workspace_id=workspace_id, display_name="Assistant", environment="development", actor_user_id=user_id)

        dataset = EvaluationDataset(organisation_id=org_id, workspace_id=workspace_id, widget_id=widget.id, name="Dataset", version="1", status="draft", created_by=user_id)
        db.add(dataset)
        db.flush()
        case = EvaluationCase(
            dataset_id=dataset.id, organisation_id=org_id, workspace_id=workspace_id,
            question="When is the deadline?", expected_answerability="answerable", category="answerable_factual",
        )
        db.add(case)
        db.commit()

        fetched_dataset = db.execute(select(EvaluationDataset).where(EvaluationDataset.id == dataset.id)).scalar_one()
        assert fetched_dataset.name == "Dataset"
        assert fetched_dataset.widget_id == widget.id

        fetched_case = db.execute(select(EvaluationCase).where(EvaluationCase.dataset_id == dataset.id)).scalar_one()
        assert fetched_case.question == "When is the deadline?"
        assert fetched_case.dataset.id == dataset.id


def test_evaluation_run_and_result_isolation_across_organisations(client: TestClient) -> None:
    org_a, workspace_a, user_a = seed_tenant(client, slug="tenant-a")
    org_b, workspace_b, user_b = seed_tenant(client, slug="tenant-b")

    with client.app.state.testing_session() as db:
        from app.access.widget_admin.service import create_widget

        widget_a = create_widget(db, organisation_id=org_a, workspace_id=workspace_a, display_name="Assistant A", environment="development", actor_user_id=user_a)
        widget_b = create_widget(db, organisation_id=org_b, workspace_id=workspace_b, display_name="Assistant B", environment="development", actor_user_id=user_b)

        dataset_a = EvaluationDataset(organisation_id=org_a, workspace_id=workspace_a, widget_id=widget_a.id, name="A", version="1", status="active")
        dataset_b = EvaluationDataset(organisation_id=org_b, workspace_id=workspace_b, widget_id=widget_b.id, name="B", version="1", status="active")
        db.add_all([dataset_a, dataset_b])
        db.flush()

        case_a = EvaluationCase(dataset_id=dataset_a.id, organisation_id=org_a, workspace_id=workspace_a, question="A?", expected_answerability="answerable", category="answerable_factual")
        case_b = EvaluationCase(dataset_id=dataset_b.id, organisation_id=org_b, workspace_id=workspace_b, question="B?", expected_answerability="answerable", category="answerable_factual")
        db.add_all([case_a, case_b])
        db.flush()

        run_a = EvaluationRun(organisation_id=org_a, workspace_id=workspace_a, widget_id=widget_a.id, dataset_id=dataset_a.id, dataset_version="1", mode="mock", status="completed", policy_snapshot_json={})
        db.add(run_a)
        db.flush()
        result_a = EvaluationResult(run_id=run_a.id, case_id=case_a.id, organisation_id=org_a, workspace_id=workspace_a, passed=True, hard_failure=False)
        db.add(result_a)
        db.commit()

        from app.repositories import evaluation_repository

        # Org B cannot see org A's dataset, run, or case via any organisation-scoped lookup.
        assert evaluation_repository.get_dataset(db, organisation_id=org_b, workspace_id=workspace_b, dataset_id=dataset_a.id) is None
        assert evaluation_repository.get_run(db, organisation_id=org_b, workspace_id=workspace_b, run_id=run_a.id) is None
        assert evaluation_repository.get_case(db, organisation_id=org_b, workspace_id=workspace_b, case_id=case_a.id) is None
        org_b_dataset_ids = {dataset.id for dataset in evaluation_repository.list_datasets(db, organisation_id=org_b, workspace_id=workspace_b)}
        assert dataset_a.id not in org_b_dataset_ids
        assert dataset_b.id in org_b_dataset_ids
        org_b_run_ids = {run.id for run in evaluation_repository.list_runs(db, organisation_id=org_b, workspace_id=workspace_b)}
        assert run_a.id not in org_b_run_ids

        # But org A can see its own records.
        assert evaluation_repository.get_dataset(db, organisation_id=org_a, workspace_id=workspace_a, dataset_id=dataset_a.id) is not None
        assert evaluation_repository.get_run(db, organisation_id=org_a, workspace_id=workspace_a, run_id=run_a.id) is not None


def test_evaluation_result_unique_per_run_and_case(client: TestClient) -> None:
    org_id, workspace_id, user_id = seed_tenant(client, slug="unique")
    with client.app.state.testing_session() as db:
        from app.access.widget_admin.service import create_widget
        from sqlalchemy.exc import IntegrityError

        widget = create_widget(db, organisation_id=org_id, workspace_id=workspace_id, display_name="Assistant", environment="development", actor_user_id=user_id)
        dataset = EvaluationDataset(organisation_id=org_id, workspace_id=workspace_id, widget_id=widget.id, name="Dataset", version="1", status="active")
        db.add(dataset)
        db.flush()
        case = EvaluationCase(dataset_id=dataset.id, organisation_id=org_id, workspace_id=workspace_id, question="Q?", expected_answerability="answerable", category="answerable_factual")
        db.add(case)
        db.flush()
        run = EvaluationRun(organisation_id=org_id, workspace_id=workspace_id, widget_id=widget.id, dataset_id=dataset.id, dataset_version="1", mode="mock", status="completed", policy_snapshot_json={})
        db.add(run)
        db.flush()
        db.add(EvaluationResult(run_id=run.id, case_id=case.id, organisation_id=org_id, workspace_id=workspace_id, passed=True, hard_failure=False))
        db.commit()

        db.add(EvaluationResult(run_id=run.id, case_id=case.id, organisation_id=org_id, workspace_id=workspace_id, passed=False, hard_failure=False))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
