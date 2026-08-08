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
from app.observability.redaction import REDACTION_RULESET_VERSION
from app.repositories import evaluation_candidate_repository

_FAKE_STRIPE_KEY = "".join(("sk", "_live_", "abcdefghijklmnopqrstuvwx"))


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


def test_secrets_are_redacted_before_persisting(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="redact-secrets")
    with client.app.state.testing_session() as db:
        candidate = evaluation_candidate_repository.create_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="manual_selection",
            severity="medium",
            question=f"Here's my Stripe key: {_FAKE_STRIPE_KEY} please help",
            response="Sure, using bearer token Bearer abcdefghijklmnop1234 now.",
            reason_code="manual",
        )
        assert _FAKE_STRIPE_KEY not in candidate.redacted_question
        assert "[redacted-stripe_secret_key]" in candidate.redacted_question
        assert "abcdefghijklmnop1234" not in candidate.redacted_response
        assert candidate.redaction_version == REDACTION_RULESET_VERSION


def test_pii_is_redacted_before_persisting(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="redact-pii")
    with client.app.state.testing_session() as db:
        candidate = evaluation_candidate_repository.create_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="support_report",
            severity="low",
            question="Contact me at jane.doe@example.com or call 555-123-4567 about my order.",
            response=None,
            reason_code="manual",
        )
        assert "jane.doe@example.com" not in candidate.redacted_question
        assert "[redacted-email]" in candidate.redacted_question


def test_evidence_refs_never_carry_quoted_chunk_content(client: TestClient) -> None:
    organisation_id, workspace_id, widget_id = seed_tenant(client, slug="redact-evidence")
    with client.app.state.testing_session() as db:
        candidate = evaluation_candidate_repository.create_candidate(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            signal_type="missing_citation",
            severity="medium",
            question="What is our refund policy?",
            response=None,
            reason_code="missing_citation",
            evidence_refs=[{"document_id": "doc-1", "chunk_id": "chunk-1", "source_title": "Refund Policy"}],
        )
        assert candidate.evidence_refs_json == [{"document_id": "doc-1", "chunk_id": "chunk-1", "source_title": "Refund Policy"}]
        for ref in candidate.evidence_refs_json:
            assert "quoted_text" not in ref
            assert set(ref.keys()) <= {"document_id", "chunk_id", "source_title"}
