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
from app.evaluation.feedback.dedup import compute_dedup_hash, find_potential_duplicates, normalize_question
from app.main import create_app
from app.repositories import evaluation_candidate_repository


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


def test_normalize_question_ignores_case_punctuation_and_whitespace() -> None:
    assert normalize_question("How do I  reset MY password?!") == normalize_question("how do i reset my password")


def test_compute_dedup_hash_is_stable_for_equivalent_questions() -> None:
    hash_a = compute_dedup_hash("How do I reset my password?", widget_id="w1", reason_code="fallback")
    hash_b = compute_dedup_hash("how do i reset my password", widget_id="w1", reason_code="fallback")
    assert hash_a == hash_b


def test_compute_dedup_hash_differs_across_assistants_and_reason_codes() -> None:
    base = compute_dedup_hash("How do I reset my password?", widget_id="w1", reason_code="fallback")
    other_widget = compute_dedup_hash("How do I reset my password?", widget_id="w2", reason_code="fallback")
    other_reason = compute_dedup_hash("How do I reset my password?", widget_id="w1", reason_code="low_confidence")
    assert base != other_widget
    assert base != other_reason


def test_second_occurrence_bumps_instead_of_creating_new_row(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="dedup-bump")
    with client.app.state.testing_session() as db:
        first = evaluation_candidate_repository.create_or_bump_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="fallback",
            severity="medium",
            question="How do I cancel my subscription?",
            response=None,
            reason_code="fallback",
        )
        assert first.created is True
        assert first.candidate.occurrence_count == 1

        second = evaluation_candidate_repository.create_or_bump_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="fallback",
            severity="medium",
            question="how do i cancel my subscription",
            response=None,
            reason_code="fallback",
        )
        assert second.created is False
        assert second.bumped is True
        assert second.candidate.id == first.candidate.id
        assert second.candidate.occurrence_count == 2


def test_find_potential_duplicates_surfaces_token_overlap_without_merging(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="dedup-suggest")
    with client.app.state.testing_session() as db:
        existing = evaluation_candidate_repository.create_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="low_confidence",
            severity="low",
            question="How can I update my billing address on file?",
            response=None,
            reason_code="low_confidence",
        )

        new_question = "How do I update my billing address on file?"
        new_dedup_hash = compute_dedup_hash(new_question, widget_id=widget_id, reason_code="low_confidence")
        suggestions = find_potential_duplicates(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            question=new_question,
            dedup_hash=new_dedup_hash,
        )
        assert any(suggestion.candidate.id == existing.id for suggestion in suggestions)
        # No auto-merge: the existing candidate is untouched.
        untouched = evaluation_candidate_repository.get_candidate(db, organisation_id=organisation_id, workspace_id=workspace_id, candidate_id=existing.id)
        assert untouched.occurrence_count == 1
        assert untouched.triage_status == "new"


def test_reopen_after_resolution_creates_new_row_flagged_as_reopen(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="dedup-reopen")
    with client.app.state.testing_session() as db:
        first = evaluation_candidate_repository.create_or_bump_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="fallback",
            severity="medium",
            question="Why was my payment declined?",
            response=None,
            reason_code="fallback",
        )
        evaluation_candidate_repository.update_triage(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            candidate_id=first.candidate.id,
            actor_user_id=None,
            triage_status="resolved",
        )

        second = evaluation_candidate_repository.create_or_bump_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="fallback",
            severity="medium",
            question="Why was my payment declined?",
            response=None,
            reason_code="fallback",
        )
        assert second.created is True
        assert second.candidate.id != first.candidate.id
        assert second.candidate.is_reopen is True
