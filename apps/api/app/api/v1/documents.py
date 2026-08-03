from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.access.widget_admin.service import (
    WidgetAdminConflict,
    WidgetAdminNotFound,
    WidgetAdminValidationError,
    get_current_draft,
    get_widget,
    update_draft_knowledge_scope,
)

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.document_repository import (
    create_document_for_workspace,
    create_uploaded_document_with_version,
    get_document_for_workspace,
    get_chunk_for_workspace,
    get_document_version_for_workspace,
    list_chunks_for_document_version,
    list_document_versions_for_workspace,
    list_documents_for_workspace,
)
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.services.chunking import (
    ChunksAlreadyExist,
    ChunkingTargetNotFound,
    InvalidChunkingStatus,
    chunk_document_version,
)
from app.services.embeddings import (
    EmbeddingProviderError,
    EmbeddingTargetNotFound,
    InvalidEmbeddingState,
    build_embedding_provider,
    embed_document_version_chunks,
)
from app.services.local_storage import LocalDocumentStorage, UnsupportedUploadType, UploadTooLarge
from app.services.manual_extraction import (
    InvalidManualExtractionStatus,
    ManualExtractionTargetNotFound,
    manually_extract_document_version,
)
from app.schemas.common import success_response
from app.services.document_lifecycle import (
    InvalidLifecycleTransition,
    LifecycleTargetNotFound,
    transition_document_status,
    transition_document_version_status,
)
from app.schemas.document import (
    ChunkRead,
    DocumentCreate,
    DocumentRead,
    DocumentVersionRead,
    LifecycleTransitionRequest,
)

router = APIRouter()

DocumentViewerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]
DocumentManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


def ensure_workspace_in_organisation(
    db: DbSession,
    *,
    organisation_id: str,
    workspace_id: str,
) -> None:
    workspace = get_workspace_for_organisation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found for organisation.",
        )


@router.get("/{workspace_id}/documents")
def list_documents(
    workspace_id: str,
    db: DbSession,
    _current_user: DocumentViewerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
    assistant_id: str | None = Query(default=None, min_length=1),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    scoped_document_ids = _assistant_document_ids(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id)
    documents = list_documents_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )
    if scoped_document_ids is not None:
        documents = [document for document in documents if document.id in scoped_document_ids]
    data = [DocumentRead.model_validate(document).model_dump(mode="json") for document in documents]
    return success_response(data, meta={"assistant_id": assistant_id} if assistant_id else None)


@router.post("/{workspace_id}/documents", status_code=status.HTTP_201_CREATED)
def create_document(
    workspace_id: str,
    payload: DocumentCreate,
    db: DbSession,
    current_user: DocumentManagerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        document = create_document_for_workspace(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=payload.title,
            source_type=payload.source_type,
            source_key=payload.source_key,
            category=payload.category,
            visibility=payload.visibility,
            metadata_json=payload.metadata_json,
            created_by_user_id=current_user.user_id,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document source identity already exists for this workspace.",
        ) from exc

    data = DocumentRead.model_validate(document).model_dump(mode="json")
    return success_response(data)


@router.post("/{workspace_id}/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: str,
    db: DbSession,
    current_user: DocumentManagerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    category: str | None = Form(default=None),
    visibility: str = Form(default="workspace"),
    assistant_id: str | None = Query(default=None, min_length=1),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    filename = file.filename or "upload"
    content = await file.read()
    storage = LocalDocumentStorage(
        root_path=settings.LOCAL_UPLOAD_ROOT,
        max_upload_bytes=settings.MAX_UPLOAD_BYTES,
    )
    try:
        stored_upload = storage.save_upload(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            filename=filename,
            content_type=file.content_type,
            content=content,
        )
    except UnsupportedUploadType as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except UploadTooLarge as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc

    try:
        document, version = create_uploaded_document_with_version(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=title or stored_upload.original_filename,
            source_type=stored_upload.source_type,
            source_key=stored_upload.relative_path,
            original_file_path=stored_upload.relative_path,
            checksum=stored_upload.checksum,
            content_type=stored_upload.content_type,
            file_size_bytes=stored_upload.size_bytes,
            original_filename=stored_upload.original_filename,
            category=category,
            visibility=visibility,
            created_by_user_id=current_user.user_id,
        )
    except IntegrityError as exc:
        db.rollback()
        storage.delete(stored_upload.relative_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document source identity already exists for this workspace.",
        ) from exc

    if assistant_id is not None:
        _assign_document_to_assistant(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id, document_id=document.id, actor_user_id=current_user.user_id)

    data = {
        "document": DocumentRead.model_validate(document).model_dump(mode="json"),
        "document_version": DocumentVersionRead.model_validate(version).model_dump(mode="json"),
    }
    return success_response(data, meta={"assistant_id": assistant_id} if assistant_id else None)

@router.get("/{workspace_id}/documents/{document_id}")
def get_document(
    workspace_id: str,
    document_id: str,
    db: DbSession,
    _current_user: DocumentViewerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    document = get_document_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for workspace.",
        )

    data = DocumentRead.model_validate(document).model_dump(mode="json")
    return success_response(data)


@router.get("/{workspace_id}/documents/{document_id}/versions")
def list_document_versions(
    workspace_id: str,
    document_id: str,
    db: DbSession,
    _current_user: DocumentViewerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    document = get_document_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for workspace.",
        )

    versions = list_document_versions_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    data = [DocumentVersionRead.model_validate(version).model_dump(mode="json") for version in versions]
    return success_response(data)


@router.get("/{workspace_id}/documents/{document_id}/versions/{version_id}")
def get_document_version(
    workspace_id: str,
    document_id: str,
    version_id: str,
    db: DbSession,
    _current_user: DocumentViewerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    document = get_document_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for workspace.",
        )

    version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=version_id,
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found for workspace.",
        )

    data = DocumentVersionRead.model_validate(version).model_dump(mode="json")
    return success_response(data)


@router.post("/{workspace_id}/documents/{document_id}/versions/{version_id}/extract")
def extract_document_version(
    workspace_id: str,
    document_id: str,
    version_id: str,
    db: DbSession,
    current_user: DocumentManagerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    storage = LocalDocumentStorage(
        root_path=settings.LOCAL_UPLOAD_ROOT,
        max_upload_bytes=settings.MAX_UPLOAD_BYTES,
    )
    try:
        result = manually_extract_document_version(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            document_version_id=version_id,
            storage=storage,
            actor_user_id=current_user.user_id,
        )
    except ManualExtractionTargetNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found for workspace.",
        ) from exc
    except InvalidManualExtractionStatus as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    data = DocumentVersionRead.model_validate(result.document_version).model_dump(mode="json")
    return success_response(
        data,
        meta={
            "success": result.success,
            "previous_status": result.previous_status,
            "new_status": result.new_status,
            "extracted_text_path": result.extracted_text_path,
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )

@router.post("/{workspace_id}/documents/{document_id}/versions/{version_id}/chunk")
def chunk_document_version_endpoint(
    workspace_id: str,
    document_id: str,
    version_id: str,
    db: DbSession,
    current_user: DocumentManagerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    storage = LocalDocumentStorage(
        root_path=settings.LOCAL_UPLOAD_ROOT,
        max_upload_bytes=settings.MAX_UPLOAD_BYTES,
    )
    try:
        result = chunk_document_version(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            document_version_id=version_id,
            storage=storage,
            chunk_size_words=settings.CHUNK_SIZE_WORDS,
            chunk_overlap_words=settings.CHUNK_OVERLAP_WORDS,
            actor_user_id=current_user.user_id,
        )
    except ChunkingTargetNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found for workspace.",
        ) from exc
    except (InvalidChunkingStatus, ChunksAlreadyExist) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    data = DocumentVersionRead.model_validate(result.document_version).model_dump(mode="json")
    return success_response(
        data,
        meta={
            "success": result.success,
            "chunk_count": result.chunk_count,
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )

@router.post("/{workspace_id}/documents/{document_id}/versions/{version_id}/embed")
def embed_document_version_endpoint(
    workspace_id: str,
    document_id: str,
    version_id: str,
    db: DbSession,
    current_user: DocumentManagerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        provider = build_embedding_provider(
            provider_name=settings.EMBEDDING_PROVIDER,
            model_name=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        result = embed_document_version_chunks(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            document_version_id=version_id,
            provider=provider,
            actor_user_id=current_user.user_id,
        )
    except EmbeddingTargetNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found for workspace.",
        ) from exc
    except InvalidEmbeddingState as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    data = DocumentVersionRead.model_validate(result.document_version).model_dump(mode="json")
    return success_response(
        data,
        meta={
            "success": result.success,
            "embedded_chunk_count": result.embedded_chunk_count,
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )

@router.get("/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks")
def list_chunks(
    workspace_id: str,
    document_id: str,
    version_id: str,
    db: DbSession,
    _current_user: DocumentViewerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    document = get_document_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for workspace.",
        )

    version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=version_id,
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found for workspace.",
        )

    chunks = list_chunks_for_document_version(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=version_id,
    )
    data = [ChunkRead.model_validate(chunk).model_dump(mode="json") for chunk in chunks]
    return success_response(data)


@router.get("/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks/{chunk_id}")
def get_chunk(
    workspace_id: str,
    document_id: str,
    version_id: str,
    chunk_id: str,
    db: DbSession,
    _current_user: DocumentViewerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    document = get_document_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for workspace.",
        )

    version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=version_id,
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found for workspace.",
        )

    chunk = get_chunk_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=version_id,
        chunk_id=chunk_id,
    )
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk not found for document version.",
        )

    data = ChunkRead.model_validate(chunk).model_dump(mode="json")
    return success_response(data)


@router.post("/{workspace_id}/documents/{document_id}/transition")
def transition_document(
    workspace_id: str,
    document_id: str,
    payload: LifecycleTransitionRequest,
    db: DbSession,
    current_user: DocumentManagerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        result = transition_document_status(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            new_status=payload.target_status,
            actor_user_id=current_user.user_id,
        )
    except LifecycleTargetNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for workspace.",
        ) from exc
    except InvalidLifecycleTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    data = DocumentRead.model_validate(result.document).model_dump(mode="json")
    return success_response(
        data,
        meta={"previous_status": result.previous_status, "new_status": result.new_status},
    )


@router.post("/{workspace_id}/documents/{document_id}/versions/{version_id}/transition")
def transition_document_version(
    workspace_id: str,
    document_id: str,
    version_id: str,
    payload: LifecycleTransitionRequest,
    db: DbSession,
    current_user: DocumentManagerDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        result = transition_document_version_status(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            document_version_id=version_id,
            new_status=payload.target_status,
            processing_error=payload.error_message,
            actor_user_id=current_user.user_id,
        )
    except LifecycleTargetNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found for workspace.",
        ) from exc
    except InvalidLifecycleTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    data = DocumentVersionRead.model_validate(result.document_version).model_dump(mode="json")
    return success_response(
        data,
        meta={"previous_status": result.previous_status, "new_status": result.new_status},
    )


def _assistant_document_ids(db: DbSession, *, organisation_id: str, workspace_id: str, assistant_id: str | None) -> set[str] | None:
    if assistant_id is None:
        return None
    assistant = _ensure_assistant(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id)
    try:
        draft = get_current_draft(db, widget=assistant)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant knowledge scope not found.") from exc
    return set(draft.knowledge_scope_json or [])


def _assign_document_to_assistant(db: DbSession, *, organisation_id: str, workspace_id: str, assistant_id: str, document_id: str, actor_user_id: str | None) -> None:
    assistant = _ensure_assistant(db, organisation_id=organisation_id, workspace_id=workspace_id, assistant_id=assistant_id)
    try:
        draft = get_current_draft(db, widget=assistant)
        document_ids = list(dict.fromkeys([*(draft.knowledge_scope_json or []), document_id]))
        update_draft_knowledge_scope(
            db,
            widget=assistant,
            actor_user_id=actor_user_id,
            document_ids=document_ids,
            expected_concurrency_version=draft.concurrency_version,
        )
    except WidgetAdminConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assistant knowledge scope changed while assigning the document.") from exc
    except WidgetAdminValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant knowledge scope not found.") from exc


def _ensure_assistant(db: DbSession, *, organisation_id: str, workspace_id: str, assistant_id: str):
    try:
        return get_widget(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=assistant_id)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found for workspace.") from exc
