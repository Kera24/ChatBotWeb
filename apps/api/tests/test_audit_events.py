from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Document, DocumentVersion, Organisation, User, Workspace
from app.repositories.audit_repository import list_audit_events_for_workspace
from app.services.document_lifecycle import (
    InvalidLifecycleTransition,
    transition_document_status,
    transition_document_version_status,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)


def seed_tenant(db_session: Session, *, slug: str) -> tuple[Organisation, Workspace, User]:
    organisation = Organisation(name=f"{slug.title()} Organisation", slug=slug)
    workspace = Workspace(organisation=organisation, name="Knowledge", slug=f"{slug}-knowledge")
    user = User(email=f"{slug}-admin@example.test")
    db_session.add_all([organisation, workspace, user])
    db_session.commit()
    return organisation, workspace, user


def seed_document_version(
    db_session: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_status: str = "uploaded",
    version_status: str = "pending",
) -> tuple[Document, DocumentVersion]:
    document = Document(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        title="Admissions Handbook",
        source_type="pdf",
        source_key=f"admissions-{uuid4()}.pdf",
        status=document_status,
    )
    version = DocumentVersion(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document=document,
        version_number=1,
        checksum=f"sha256:{uuid4()}",
        processing_status=version_status,
    )
    db_session.add_all([document, version])
    db_session.commit()
    return document, version


def test_document_lifecycle_transition_creates_audit_event(db_session: Session) -> None:
    organisation, workspace, user = seed_tenant(db_session, slug="alpha")
    document, _version = seed_document_version(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
    )

    transition_document_status(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        document_id=document.id,
        new_status="processing",
        actor_user_id=user.id,
    )

    events = list_audit_events_for_workspace(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.action == "document.status.transitioned"
    assert event.entity_type == "document"
    assert event.entity_id == document.id
    assert event.document_id == document.id
    assert event.document_version_id is None
    assert event.actor_user_id == user.id
    assert event.previous_status == "uploaded"
    assert event.new_status == "processing"
    assert event.metadata_json == {"status_field": "status"}


def test_document_version_lifecycle_transition_creates_audit_event(db_session: Session) -> None:
    organisation, workspace, user = seed_tenant(db_session, slug="alpha")
    document, version = seed_document_version(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        version_status="pending",
    )

    transition_document_version_status(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        document_id=document.id,
        document_version_id=version.id,
        new_status="queued",
        actor_user_id=user.id,
    )

    events = list_audit_events_for_workspace(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.action == "document_version.processing_status.transitioned"
    assert event.entity_type == "document_version"
    assert event.entity_id == version.id
    assert event.document_id == document.id
    assert event.document_version_id == version.id
    assert event.actor_user_id == user.id
    assert event.previous_status == "pending"
    assert event.new_status == "queued"
    assert event.metadata_json == {"status_field": "processing_status"}


def test_invalid_lifecycle_transition_does_not_create_audit_event(db_session: Session) -> None:
    organisation, workspace, user = seed_tenant(db_session, slug="alpha")
    document, _version = seed_document_version(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        document_status="uploaded",
    )

    with pytest.raises(InvalidLifecycleTransition):
        transition_document_status(
            db_session,
            organisation_id=organisation.id,
            workspace_id=workspace.id,
            document_id=document.id,
            new_status="ready",
            actor_user_id=user.id,
        )

    events = list_audit_events_for_workspace(
        db_session,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
    )
    assert events == []


def test_audit_events_remain_tenant_scoped(db_session: Session) -> None:
    org_a, workspace_a, user_a = seed_tenant(db_session, slug="alpha")
    org_b, workspace_b, user_b = seed_tenant(db_session, slug="beta")
    document_a, _version_a = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
    )
    document_b, _version_b = seed_document_version(
        db_session,
        organisation_id=org_b.id,
        workspace_id=workspace_b.id,
    )

    transition_document_status(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document_a.id,
        new_status="processing",
        actor_user_id=user_a.id,
    )
    transition_document_status(
        db_session,
        organisation_id=org_b.id,
        workspace_id=workspace_b.id,
        document_id=document_b.id,
        new_status="processing",
        actor_user_id=user_b.id,
    )

    org_a_events = list_audit_events_for_workspace(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
    )
    org_b_events = list_audit_events_for_workspace(
        db_session,
        organisation_id=org_b.id,
        workspace_id=workspace_b.id,
    )
    wrong_scope_events = list_audit_events_for_workspace(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_b.id,
    )

    assert [event.document_id for event in org_a_events] == [document_a.id]
    assert [event.document_id for event in org_b_events] == [document_b.id]
    assert wrong_scope_events == []
