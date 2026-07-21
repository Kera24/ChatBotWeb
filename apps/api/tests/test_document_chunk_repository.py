import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Organisation, Workspace
from app.repositories.document_repository import (
    create_chunk_for_workspace,
    create_document_for_workspace,
    create_document_version_for_workspace,
    get_chunk_for_workspace,
    get_document_for_workspace,
    list_documents_for_workspace,
    list_ready_chunks_for_workspace,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)


def seed_document_chunk(db_session: Session):
    org_a = Organisation(name="Alpha College", slug="alpha")
    org_b = Organisation(name="Beta Clinic", slug="beta")
    workspace_a = Workspace(organisation=org_a, name="Admissions", slug="admissions")
    workspace_b = Workspace(organisation=org_b, name="Patient Help", slug="patient-help")
    db_session.add_all([org_a, org_b, workspace_a, workspace_b])
    db_session.commit()

    document = create_document_for_workspace(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        title="Admissions Handbook",
        source_type="pdf",
        source_key="admissions-handbook.pdf",
    )
    version = create_document_version_for_workspace(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        version_number=1,
        checksum="sha256:abc123",
    )
    chunk = create_chunk_for_workspace(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_index=0,
        content="Applications close in December.",
        content_hash="sha256:chunk123",
        source_type="pdf",
        source_title="Admissions Handbook",
        status="ready",
    )
    return org_a, org_b, workspace_a, workspace_b, document, version, chunk


def test_document_lookup_requires_organisation_and_workspace(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b, document, _version, _chunk = seed_document_chunk(db_session)

    correct = get_document_for_workspace(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, document_id=document.id)
    wrong_org = get_document_for_workspace(db_session, organisation_id=org_b.id, workspace_id=workspace_a.id, document_id=document.id)
    wrong_workspace = get_document_for_workspace(db_session, organisation_id=org_a.id, workspace_id=workspace_b.id, document_id=document.id)

    assert correct is not None
    assert wrong_org is None
    assert wrong_workspace is None


def test_document_list_stays_inside_workspace_scope(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b, document, _version, _chunk = seed_document_chunk(db_session)

    org_a_documents = list_documents_for_workspace(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id)
    org_b_documents = list_documents_for_workspace(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id)

    assert [item.id for item in org_a_documents] == [document.id]
    assert org_b_documents == []


def test_chunk_lookup_requires_full_tenant_document_version_scope(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b, document, version, chunk = seed_document_chunk(db_session)

    correct = get_chunk_for_workspace(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_id=chunk.id,
    )
    wrong_org = get_chunk_for_workspace(
        db_session,
        organisation_id=org_b.id,
        workspace_id=workspace_a.id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_id=chunk.id,
    )
    wrong_workspace = get_chunk_for_workspace(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_b.id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_id=chunk.id,
    )

    assert correct is not None
    assert wrong_org is None
    assert wrong_workspace is None


def test_ready_chunk_listing_requires_ready_document_version_and_chunk(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b, document, version, chunk = seed_document_chunk(db_session)
    document.status = "ready"
    version.processing_status = "ready"
    db_session.commit()

    org_a_chunks = list_ready_chunks_for_workspace(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id)
    org_b_chunks = list_ready_chunks_for_workspace(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id)

    assert [item.id for item in org_a_chunks] == [chunk.id]
    assert org_b_chunks == []
