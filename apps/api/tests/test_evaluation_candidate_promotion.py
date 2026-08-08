from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app
from app.repositories import evaluation_candidate_repository, evaluation_repository
from app.repositories.evaluation_candidate_repository import CandidateNotAccepted


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


def test_promotion_requires_accepted_status(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="promote-guard")
    with client.app.state.testing_session() as db:
        dataset = evaluation_repository.create_dataset(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, name="Golden", description=None, version="1", created_by=None
        )
        candidate = evaluation_candidate_repository.create_candidate(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, signal_type="fallback", severity="medium",
            question="How do I export my data?", response=None, reason_code="fallback",
        )

        with pytest.raises(CandidateNotAccepted):
            evaluation_candidate_repository.promote_candidate(
                db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate.id, dataset_id=dataset.id,
                reviewer_id=None, changelog_note="should fail",
            )


def test_promotion_creates_case_with_redacted_content_and_provenance(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="promote-success")
    with client.app.state.testing_session() as db:
        dataset = evaluation_repository.create_dataset(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, name="Golden", description=None, version="1", created_by=None
        )
        candidate = evaluation_candidate_repository.create_candidate(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, signal_type="fallback", severity="high",
            question="What is our contact email support@internal-example.com?", response="Reach out at support@internal-example.com.",
            reason_code="fallback",
        )
        evaluation_candidate_repository.update_triage(
            db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate.id, actor_user_id=None,
            triage_status="accepted", root_cause_category="citation_required", expected_answerability="answerable",
        )

        candidate, case, version_event = evaluation_candidate_repository.promote_candidate(
            db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate.id, dataset_id=dataset.id,
            reviewer_id=None, changelog_note="promoting a production failure",
        )

        assert case.question == candidate.redacted_question
        assert "[redacted-email]" in case.question
        assert case.category == "citation_required"
        assert case.source_candidate_id == candidate.id
        assert case.metadata_json["source_candidate_id"] == candidate.id

        assert candidate.promoted_case_id == case.id
        assert candidate.dataset_destination_id == dataset.id

        assert version_event.from_version == "1"
        assert version_event.to_version == "2"
        assert version_event.case_id == case.id
        assert version_event.candidate_id == candidate.id

        refreshed_dataset = evaluation_repository.get_dataset(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=dataset.id)
        assert refreshed_dataset.version == "2"


def test_promotion_does_not_mutate_existing_runs(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="promote-no-mutate")
    with client.app.state.testing_session() as db:
        dataset = evaluation_repository.create_dataset(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, name="Golden", description=None, version="1", created_by=None
        )
        existing_run = evaluation_repository.create_run(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, dataset=dataset, mode="mock",
            policy_snapshot={}, retrieval_settings=None, created_by=None,
        )
        assert existing_run.dataset_version == "1"

        candidate = evaluation_candidate_repository.create_candidate(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, signal_type="fallback", severity="medium",
            question="What is our refund window?", response=None, reason_code="fallback",
        )
        evaluation_candidate_repository.update_triage(
            db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate.id, actor_user_id=None, triage_status="accepted",
        )
        evaluation_candidate_repository.promote_candidate(
            db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=candidate.id, dataset_id=dataset.id,
            reviewer_id=None, changelog_note=None,
        )

        reloaded_run = evaluation_repository.get_run(db, organisation_id=organisation_id, workspace_id=workspace_id, run_id=existing_run.id)
        assert reloaded_run.dataset_version == "1"
