from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.orm import Session

from app.db.models import Chunk, DocumentVersion
from app.repositories.audit_repository import add_audit_event
from app.repositories.document_repository import (
    get_document_version_for_workspace,
    list_chunks_for_document_version,
)
from app.services.local_storage import LocalDocumentStorage

CHUNKING_STRATEGY_VERSION = "mvp-word-v1"


class ChunkingTargetNotFound(LookupError):
    pass


class InvalidChunkingStatus(ValueError):
    pass


class MissingExtractedTextPath(ValueError):
    pass


class ChunksAlreadyExist(ValueError):
    pass


@dataclass(frozen=True)
class ChunkingResult:
    document_version: DocumentVersion
    success: bool
    chunk_count: int
    error_code: str | None = None
    error_message: str | None = None


def chunk_document_version(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
    storage: LocalDocumentStorage,
    chunk_size_words: int,
    chunk_overlap_words: int,
    actor_user_id: str | None = None,
) -> ChunkingResult:
    version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
    )
    if version is None:
        raise ChunkingTargetNotFound("Document version not found for tenant workspace.")

    if version.processing_status != "ready":
        raise InvalidChunkingStatus(
            f"Chunking requires processing_status 'ready', got {version.processing_status!r}."
        )

    if version.extracted_text_path is None:
        return _fail(
            db,
            version=version,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            actor_user_id=actor_user_id,
            error_code="EXTRACTED_TEXT_MISSING",
            error_message="Document version does not have an extracted text path.",
        )

    existing_chunks = list_chunks_for_document_version(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
    )
    if existing_chunks:
        raise ChunksAlreadyExist("Chunks already exist for this document version.")

    try:
        extracted_path = storage.resolve_path(version.extracted_text_path)
        text = extracted_path.read_text(encoding="utf-8")
    except Exception:
        return _fail(
            db,
            version=version,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            actor_user_id=actor_user_id,
            error_code="EXTRACTED_TEXT_READ_FAILED",
            error_message="Extracted text artifact could not be read safely.",
        )

    chunks = split_text_into_chunks(
        text,
        chunk_size_words=chunk_size_words,
        chunk_overlap_words=chunk_overlap_words,
    )
    for chunk_index, chunk_text in enumerate(chunks):
        db.add(
            Chunk(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                document_id=document_id,
                document_version_id=document_version_id,
                chunk_index=chunk_index,
                content=chunk_text,
                content_hash=sha256(chunk_text.encode("utf-8")).hexdigest(),
                token_count=len(chunk_text.split()),
                source_type=version.document.source_type,
                source_title=version.document.title,
                chunking_strategy_version=CHUNKING_STRATEGY_VERSION,
                status="ready",
                metadata_json={
                    "chunk_size_words": chunk_size_words,
                    "chunk_overlap_words": chunk_overlap_words,
                },
            )
        )

    metadata_json = dict(version.metadata_json or {})
    metadata_json["chunking"] = {
        "strategy": CHUNKING_STRATEGY_VERSION,
        "chunk_count": len(chunks),
        "chunk_size_words": chunk_size_words,
        "chunk_overlap_words": chunk_overlap_words,
    }
    version.metadata_json = metadata_json
    db.add(version)
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="document_version.chunking.succeeded",
        entity_type="document_version",
        entity_id=version.id,
        document_id=document_id,
        document_version_id=version.id,
        previous_status=version.processing_status,
        new_status=version.processing_status,
        metadata_json={"chunk_count": len(chunks), "strategy": CHUNKING_STRATEGY_VERSION},
    )
    db.commit()
    db.refresh(version)
    return ChunkingResult(document_version=version, success=True, chunk_count=len(chunks))


def split_text_into_chunks(
    text: str,
    *,
    chunk_size_words: int,
    chunk_overlap_words: int,
) -> list[str]:
    if chunk_size_words <= 0:
        raise ValueError("chunk_size_words must be positive.")
    if chunk_overlap_words < 0:
        raise ValueError("chunk_overlap_words must be non-negative.")
    if chunk_overlap_words >= chunk_size_words:
        raise ValueError("chunk_overlap_words must be smaller than chunk_size_words.")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    step = chunk_size_words - chunk_overlap_words
    while start < len(words):
        end = min(start + chunk_size_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks


def _fail(
    db: Session,
    *,
    version: DocumentVersion,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    actor_user_id: str | None,
    error_code: str,
    error_message: str,
) -> ChunkingResult:
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="document_version.chunking.failed",
        entity_type="document_version",
        entity_id=version.id,
        document_id=document_id,
        document_version_id=version.id,
        previous_status=version.processing_status,
        new_status=version.processing_status,
        metadata_json={"error_code": error_code},
    )
    db.commit()
    db.refresh(version)
    return ChunkingResult(
        document_version=version,
        success=False,
        chunk_count=0,
        error_code=error_code,
        error_message=error_message,
    )
