from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentVersion
from app.repositories.audit_repository import add_audit_event


def create_document_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    title: str,
    source_type: str,
    source_key: str | None = None,
    visibility: str = "workspace",
    category: str | None = None,
    metadata_json: dict | None = None,
    created_by_user_id: str | None = None,
) -> Document:
    document = Document(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        title=title,
        source_type=source_type,
        source_key=source_key,
        visibility=visibility,
        category=category,
        metadata_json=metadata_json,
        created_by_user_id=created_by_user_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    include_deleted: bool = False,
) -> Document | None:
    statement = select(Document).where(
        Document.id == document_id,
        Document.organisation_id == organisation_id,
        Document.workspace_id == workspace_id,
    )
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    return db.execute(statement).scalar_one_or_none()


def list_documents_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    status: str | None = None,
) -> list[Document]:
    statement = select(Document).where(
        Document.organisation_id == organisation_id,
        Document.workspace_id == workspace_id,
        Document.deleted_at.is_(None),
    )
    if status is not None:
        statement = statement.where(Document.status == status)
    statement = statement.order_by(Document.title)
    return list(db.execute(statement).scalars().all())


def create_document_version_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    version_number: int,
    checksum: str,
    metadata_json: dict | None = None,
) -> DocumentVersion:
    document = get_document_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if document is None:
        raise ValueError("document does not exist in tenant workspace")

    version = DocumentVersion(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        version_number=version_number,
        checksum=checksum,
        metadata_json=metadata_json,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version



def create_uploaded_document_with_version(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    title: str,
    source_type: str,
    source_key: str,
    original_file_path: str,
    checksum: str,
    content_type: str | None,
    file_size_bytes: int,
    original_filename: str,
    category: str | None = None,
    visibility: str = "workspace",
    created_by_user_id: str | None = None,
) -> tuple[Document, DocumentVersion]:
    document = Document(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        title=title,
        source_type=source_type,
        source_key=source_key,
        status="uploaded",
        visibility=visibility,
        category=category,
        created_by_user_id=created_by_user_id,
        metadata_json={
            "original_filename": original_filename,
            "content_type": content_type,
            "file_size_bytes": file_size_bytes,
            "checksum": checksum,
        },
    )
    db.add(document)
    db.flush()

    version = DocumentVersion(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document.id,
        version_number=1,
        original_file_path=original_file_path,
        checksum=checksum,
        processing_status="uploaded",
        created_by_user_id=created_by_user_id,
        metadata_json={
            "original_filename": original_filename,
            "content_type": content_type,
            "file_size_bytes": file_size_bytes,
        },
    )
    db.add(version)
    db.flush()

    document.active_document_version_id = version.id
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=created_by_user_id,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        document_id=document.id,
        document_version_id=version.id,
        new_status="uploaded",
        metadata_json={
            "original_filename": original_filename,
            "content_type": content_type,
            "file_size_bytes": file_size_bytes,
        },
    )
    db.commit()
    db.refresh(document)
    db.refresh(version)
    return document, version


def list_document_versions_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
) -> list[DocumentVersion]:
    statement = (
        select(DocumentVersion)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(
            DocumentVersion.organisation_id == organisation_id,
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document_id,
            Document.organisation_id == organisation_id,
            Document.workspace_id == workspace_id,
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
        .order_by(DocumentVersion.version_number.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_document_version_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
) -> DocumentVersion | None:
    statement = select(DocumentVersion).where(
        DocumentVersion.id == document_version_id,
        DocumentVersion.document_id == document_id,
        DocumentVersion.organisation_id == organisation_id,
        DocumentVersion.workspace_id == workspace_id,
    )
    return db.execute(statement).scalar_one_or_none()


def create_chunk_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
    chunk_index: int,
    content: str,
    content_hash: str,
    source_type: str,
    source_title: str,
    status: str = "pending",
    metadata_json: dict | None = None,
) -> Chunk:
    version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
    )
    if version is None:
        raise ValueError("document version does not exist in tenant workspace")

    chunk = Chunk(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
        chunk_index=chunk_index,
        content=content,
        content_hash=content_hash,
        source_type=source_type,
        source_title=source_title,
        status=status,
        metadata_json=metadata_json,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def list_chunks_for_document_version(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
) -> list[Chunk]:
    statement = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .where(
            Chunk.organisation_id == organisation_id,
            Chunk.workspace_id == workspace_id,
            Chunk.document_id == document_id,
            Chunk.document_version_id == document_version_id,
            Document.organisation_id == organisation_id,
            Document.workspace_id == workspace_id,
            Document.id == document_id,
            Document.deleted_at.is_(None),
            DocumentVersion.organisation_id == organisation_id,
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.document_id == document_id,
            DocumentVersion.id == document_version_id,
        )
        .order_by(Chunk.chunk_index)
    )
    return list(db.execute(statement).scalars().all())


def get_chunk_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
    chunk_id: str,
) -> Chunk | None:
    statement = select(Chunk).where(
        Chunk.id == chunk_id,
        Chunk.organisation_id == organisation_id,
        Chunk.workspace_id == workspace_id,
        Chunk.document_id == document_id,
        Chunk.document_version_id == document_version_id,
    )
    return db.execute(statement).scalar_one_or_none()


def list_ready_chunks_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str | None = None,
) -> list[Chunk]:
    statement = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .where(
            Chunk.organisation_id == organisation_id,
            Chunk.workspace_id == workspace_id,
            Chunk.status == "ready",
            Document.organisation_id == organisation_id,
            Document.workspace_id == workspace_id,
            Document.status == "ready",
            Document.deleted_at.is_(None),
            DocumentVersion.organisation_id == organisation_id,
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.processing_status == "ready",
        )
    )
    if document_id is not None:
        statement = statement.where(Chunk.document_id == document_id)
    statement = statement.order_by(Chunk.document_id, Chunk.chunk_index)
    return list(db.execute(statement).scalars().all())
