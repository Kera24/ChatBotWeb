import pytest
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Document, DocumentVersion, Organisation, Workspace
from app.services.document_lifecycle import (
    InvalidLifecycleTransition,
    LifecycleTargetNotFound,
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


def seed_tenants(db_session: Session) -> tuple[Organisation, Organisation, Workspace, Workspace]:
    org_a = Organisation(name="Alpha College", slug="alpha")
    org_b = Organisation(name="Beta Clinic", slug="beta")
    workspace_a = Workspace(organisation=org_a, name="Admissions", slug="admissions")
    workspace_b = Workspace(organisation=org_b, name="Patient Help", slug="patient-help")
    db_session.add_all([org_a, org_b, workspace_a, workspace_b])
    db_session.commit()
    return org_a, org_b, workspace_a, workspace_b


def seed_document_version(
    db_session: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_status: str = "uploaded",
    version_status: str = "pending",
) -> tuple[Document, DocumentVersion]:
    source_key = f"admissions-handbook-{uuid4()}.pdf"
    document = Document(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        title="Admissions Handbook",
        source_type="pdf",
        source_key=source_key,
        status=document_status,
    )
    version = DocumentVersion(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document=document,
        version_number=1,
        checksum="sha256:abc123",
        processing_status=version_status,
    )
    db_session.add_all([document, version])
    db_session.commit()
    return document, version


def test_valid_document_status_transitions(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    document, _version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
    )

    processing = transition_document_status(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        new_status="processing",
    )
    ready = transition_document_status(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        new_status="ready",
    )

    assert processing.previous_status == "uploaded"
    assert processing.new_status == "processing"
    assert ready.previous_status == "processing"
    assert ready.document.status == "ready"


def test_document_processing_can_fail(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    document, _version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_status="processing",
    )

    result = transition_document_status(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        new_status="failed",
    )

    assert result.previous_status == "processing"
    assert result.document.status == "failed"


def test_invalid_document_transition_is_rejected(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    document, _version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_status="uploaded",
    )

    with pytest.raises(InvalidLifecycleTransition):
        transition_document_status(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            document_id=document.id,
            new_status="ready",
        )

    db_session.refresh(document)
    assert document.status == "uploaded"


def test_cross_tenant_document_transition_is_denied(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b = seed_tenants(db_session)
    document, _version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
    )

    with pytest.raises(LifecycleTargetNotFound):
        transition_document_status(
            db_session,
            organisation_id=org_b.id,
            workspace_id=workspace_b.id,
            document_id=document.id,
            new_status="processing",
        )

    db_session.refresh(document)
    assert document.status == "uploaded"


def test_archived_and_expired_documents_are_terminal(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    archived_doc, _archived_version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_status="ready",
    )
    expired_doc, _expired_version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_status="ready",
    )

    archived = transition_document_status(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=archived_doc.id,
        new_status="archived",
    )
    expired = transition_document_status(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=expired_doc.id,
        new_status="expired",
    )

    assert archived.document.archived_at is not None
    assert expired.document.expires_at is not None
    with pytest.raises(InvalidLifecycleTransition):
        transition_document_status(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            document_id=archived_doc.id,
            new_status="ready",
        )
    with pytest.raises(InvalidLifecycleTransition):
        transition_document_status(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            document_id=expired_doc.id,
            new_status="ready",
        )


def test_valid_document_version_status_transitions(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    document, version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
    )

    for status in ["queued", "extracting", "chunking", "embedding", "ready"]:
        result = transition_document_version_status(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            document_id=document.id,
            document_version_id=version.id,
            new_status=status,
        )
        assert result.new_status == status

    db_session.refresh(version)
    assert version.processing_status == "ready"


def test_document_version_processing_can_fail_with_safe_error(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    document, version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        version_status="chunking",
    )

    result = transition_document_version_status(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        document_version_id=version.id,
        new_status="failed",
        processing_error="Text extraction failed.",
    )

    assert result.previous_status == "chunking"
    assert result.document_version.processing_status == "failed"
    assert result.document_version.processing_error == "Text extraction failed."


def test_invalid_document_version_transition_is_rejected(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    document, version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        version_status="pending",
    )

    with pytest.raises(InvalidLifecycleTransition):
        transition_document_version_status(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            document_id=document.id,
            document_version_id=version.id,
            new_status="ready",
        )

    db_session.refresh(version)
    assert version.processing_status == "pending"


def test_cross_tenant_document_version_transition_is_denied(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b = seed_tenants(db_session)
    document, version = seed_document_version(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
    )

    with pytest.raises(LifecycleTargetNotFound):
        transition_document_version_status(
            db_session,
            organisation_id=org_b.id,
            workspace_id=workspace_b.id,
            document_id=document.id,
            document_version_id=version.id,
            new_status="queued",
        )

    db_session.refresh(version)
    assert version.processing_status == "pending"
