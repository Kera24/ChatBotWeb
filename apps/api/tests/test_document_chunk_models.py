import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Organisation, Workspace


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)


def test_can_create_document_version_and_chunk_models(db_session: Session) -> None:
    organisation = Organisation(name="Example College", slug="example-college")
    workspace = Workspace(organisation=organisation, name="Admissions", slug="admissions")
    db_session.add_all([organisation, workspace])
    db_session.flush()

    document = Document(
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        title="Admissions Handbook",
        source_type="pdf",
        source_key="handbook.pdf",
        metadata_json={"language": "en", "tags": ["admissions"]},
    )
    version = DocumentVersion(
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        document=document,
        version_number=1,
        checksum="sha256:abc123",
        metadata_json={"mime_type": "application/pdf", "parser_name": "placeholder"},
    )
    chunk = Chunk(
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        document=document,
        document_version=version,
        chunk_index=0,
        content="Apply before the deadline.",
        content_hash="sha256:chunk123",
        source_type="pdf",
        source_title="Admissions Handbook",
        status="ready",
        metadata_json={"page_number": 1},
    )

    db_session.add_all([document, version, chunk])
    db_session.commit()

    assert document.status == "uploaded"
    assert document.visibility == "workspace"
    assert version.processing_status == "pending"
    assert chunk.document_id == document.id
    assert chunk.document_version_id == version.id
    assert chunk.organisation_id == organisation.id
    assert chunk.workspace_id == workspace.id
