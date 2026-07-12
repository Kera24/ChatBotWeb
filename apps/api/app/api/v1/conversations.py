from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.conversation_repository import (
    get_conversation_detail,
    list_citations_for_messages,
    list_conversation_summaries,
    list_messages,
)
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.conversation import (
    ConversationCitationRead,
    ConversationDetailRead,
    ConversationMessageRead,
    ConversationSummaryRead,
)

router = APIRouter()

ConversationViewerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]

MAX_CONVERSATION_HISTORY_LIMIT = 100


@router.get("/{workspace_id}/conversations")
def list_workspace_conversations(
    workspace_id: str,
    db: DbSession,
    _current_user: ConversationViewerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
    status_filter: str | None = Query(default=None, alias="status"),
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_CONVERSATION_HISTORY_LIMIT),
    offset: int = Query(default=0, ge=0),
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    rows = list_conversation_summaries(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        status=status_filter,
        channel=channel,
        limit=limit,
        offset=offset,
        started_after=started_after,
        started_before=started_before,
    )
    data = [
        ConversationSummaryRead(
            id=row.conversation.id,
            organisation_id=row.conversation.organisation_id,
            workspace_id=row.conversation.workspace_id,
            channel=row.conversation.channel,
            status=row.conversation.status,
            title=row.conversation.title,
            started_at=row.conversation.started_at,
            last_message_at=row.conversation.last_message_at,
            ended_at=row.conversation.ended_at,
            message_count=row.message_count,
            last_message_preview=row.last_message_preview,
            metadata=row.conversation.metadata_json,
        ).model_dump(mode="json")
        for row in rows
    ]
    return success_response(data, meta={"limit": limit, "offset": offset})


@router.get("/{workspace_id}/conversations/{conversation_id}")
def get_workspace_conversation_detail(
    workspace_id: str,
    conversation_id: str,
    db: DbSession,
    _current_user: ConversationViewerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    conversation = get_conversation_detail(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found for workspace.")

    messages = list_messages(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
    )
    citations_by_message = list_citations_for_messages(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        message_ids=[message.id for message in messages],
    )
    data = ConversationDetailRead(
        id=conversation.id,
        organisation_id=conversation.organisation_id,
        workspace_id=conversation.workspace_id,
        channel=conversation.channel,
        status=conversation.status,
        title=conversation.title,
        started_at=conversation.started_at,
        last_message_at=conversation.last_message_at,
        ended_at=conversation.ended_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        metadata=conversation.metadata_json,
        messages=[_message_response(message, citations_by_message.get(message.id, [])) for message in messages],
    )
    return success_response(data.model_dump(mode="json"))


def _ensure_workspace(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


def _message_response(message, citations) -> ConversationMessageRead:
    return ConversationMessageRead(
        id=message.id,
        role=message.role,
        content=message.content,
        sequence_number=message.sequence_number,
        answer_state=message.answer_state,
        model_key=message.model_key,
        provider_key=message.provider_key,
        provider_model_name=message.provider_model_name,
        prompt_key=message.prompt_key,
        prompt_version=message.prompt_version,
        prompt_hash=message.prompt_hash,
        execution_id=message.execution_id,
        input_tokens=message.input_tokens,
        output_tokens=message.output_tokens,
        total_tokens=message.total_tokens,
        estimated_cost=message.estimated_cost,
        latency_ms=message.latency_ms,
        finish_reason=message.finish_reason,
        error_code=message.error_code,
        created_at=message.created_at,
        citations=[
            ConversationCitationRead(
                id=citation.id,
                citation_index=citation.citation_index,
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                document_version_id=citation.document_version_id,
                similarity_score=citation.similarity_score,
                source_title=citation.source_title,
                source_type=citation.source_type,
                page_number=citation.page_number,
                section_title=citation.section_title,
                quoted_text=citation.quoted_text,
                created_at=citation.created_at,
            )
            for citation in citations
        ],
    )
