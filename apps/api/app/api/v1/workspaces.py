from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.prompt import RetrievalPromptRequest, RetrievalPromptResponse
from app.schemas.retrieval import (
    RetrievalCitation,
    RetrievalContextBlock,
    RetrievalContextRequest,
    RetrievalContextResponse,
)
from app.schemas.search import VectorSearchRequest, VectorSearchResult
from app.schemas.workspace import WorkspaceRead
from app.services.embeddings import EmbeddingProviderError, build_embedding_provider
from app.services.prompt_assembly import assemble_grounded_prompt
from app.services.retrieval_context import assemble_retrieval_context
from app.services.vector_search import search_embedded_chunks
from app.core.config import settings

router = APIRouter()

WorkspaceViewerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]


@router.post("/{workspace_id}/retrieval/prompt")
def assemble_workspace_retrieval_prompt(
    workspace_id: str,
    payload: RetrievalPromptRequest,
    db: DbSession,
    _current_user: WorkspaceViewerDependency,
    organisation_id: str = Query(
        ...,
        description=(
            "Temporary tenant context required until production auth can infer "
            "organisation access safely."
        ),
    ),
) -> dict[str, object]:
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

    try:
        provider = build_embedding_provider(
            provider_name=settings.EMBEDDING_PROVIDER,
            model_name=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        result = assemble_grounded_prompt(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            query=payload.query,
            search_limit=payload.limit,
            max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
            max_context_chars=payload.max_context_chars or settings.RETRIEVAL_MAX_CONTEXT_CHARS,
            provider=provider,
            prompt_version=settings.PROMPT_VERSION,
        )
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    response_data = RetrievalPromptResponse(
        prompt_version=result.prompt_version,
        system_prompt=result.system_prompt,
        user_prompt=result.user_prompt,
        context_blocks=[
            RetrievalContextBlock(**block.__dict__) for block in result.context_blocks
        ],
        citations=[RetrievalCitation(**citation.__dict__) for citation in result.citations],
    )
    return success_response(response_data.model_dump(mode="json"))

@router.post("/{workspace_id}/retrieval/context")
def assemble_workspace_retrieval_context(
    workspace_id: str,
    payload: RetrievalContextRequest,
    db: DbSession,
    _current_user: WorkspaceViewerDependency,
    organisation_id: str = Query(
        ...,
        description=(
            "Temporary tenant context required until production auth can infer "
            "organisation access safely."
        ),
    ),
) -> dict[str, object]:
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

    try:
        provider = build_embedding_provider(
            provider_name=settings.EMBEDDING_PROVIDER,
            model_name=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        result = assemble_retrieval_context(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            query=payload.query,
            search_limit=payload.limit,
            max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
            max_context_chars=payload.max_context_chars or settings.RETRIEVAL_MAX_CONTEXT_CHARS,
            provider=provider,
        )
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    response_data = RetrievalContextResponse(
        query=result.query,
        context_blocks=[
            RetrievalContextBlock(**block.__dict__) for block in result.context_blocks
        ],
        citations=[RetrievalCitation(**citation.__dict__) for citation in result.citations],
        total_context_chars=result.total_context_chars,
    )
    return success_response(response_data.model_dump(mode="json"))

@router.post("/{workspace_id}/search")
def search_workspace_chunks(
    workspace_id: str,
    payload: VectorSearchRequest,
    db: DbSession,
    _current_user: WorkspaceViewerDependency,
    organisation_id: str = Query(
        ...,
        description=(
            "Temporary tenant context required until production auth can infer "
            "organisation access safely."
        ),
    ),
) -> dict[str, object]:
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

    try:
        provider = build_embedding_provider(
            provider_name=settings.EMBEDDING_PROVIDER,
            model_name=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        matches = search_embedded_chunks(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            query=payload.query,
            limit=payload.limit,
            provider=provider,
        )
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    data = [
        VectorSearchResult(
            chunk_id=match.chunk_id,
            document_id=match.document_id,
            document_version_id=match.document_version_id,
            chunk_index=match.chunk_index,
            content=match.content,
            score=match.score,
            source_type=match.source_type,
            source_title=match.source_title,
            page_number=match.page_number,
            section_title=match.section_title,
            heading_path=match.heading_path,
            metadata_json=match.metadata_json,
        ).model_dump(mode="json")
        for match in matches
    ]
    return success_response(data, meta={"query": payload.query, "limit": payload.limit})

@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: str,
    db: DbSession,
    _current_user: WorkspaceViewerDependency,
    organisation_id: str = Query(
        ...,
        description=(
            "Temporary tenant context required until production auth can infer "
            "organisation access safely."
        ),
    ),
) -> dict[str, object]:
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

    data = WorkspaceRead.model_validate(workspace).model_dump(mode="json")
    return success_response(data)
