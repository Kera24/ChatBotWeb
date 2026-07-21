from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.api.v1.conversations import _message_response
from app.repositories.conversation_repository import list_citations_for_messages, list_messages
from app.repositories.review_repository import (
    InvalidReviewStatus,
    REVIEW_ANSWER_STATES,
    REVIEW_STATUSES,
    ReviewItemNotFound,
    count_review_items,
    get_review_item_detail,
    list_citations_for_review_item,
    list_review_items,
    update_review_status,
)
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.conversation import ConversationCitationRead
from app.schemas.review import ReviewItemDetailRead, ReviewItemRead, ReviewStatusUpdate

router = APIRouter()

ReviewReaderDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]
ReviewUpdaterDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]

MAX_REVIEW_LIMIT = 100


@router.get("/{workspace_id}/review/unanswered")
def list_unanswered_review_items(
    workspace_id: str,
    db: DbSession,
    _current_user: ReviewReaderDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
    answer_state: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_REVIEW_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    _validate_filters(answer_state=answer_state, review_status=review_status)
    rows = list_review_items(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        answer_state=answer_state,
        review_status=review_status,
        channel=channel,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )
    total = count_review_items(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        answer_state=answer_state,
        review_status=review_status,
        channel=channel,
        created_after=created_after,
        created_before=created_before,
    )
    data = [_review_item_response(db, organisation_id=organisation_id, workspace_id=workspace_id, row=row) for row in rows]
    return success_response([item.model_dump(mode="json") for item in data], meta={"limit": limit, "offset": offset, "count": len(data), "total": total})


@router.get("/{workspace_id}/review/unanswered/{assistant_message_id}")
def get_unanswered_review_item(
    workspace_id: str,
    assistant_message_id: str,
    db: DbSession,
    _current_user: ReviewReaderDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    row = get_review_item_detail(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        assistant_message_id=assistant_message_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found for workspace.")

    messages = list_messages(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=row.conversation.id,
    )
    citations_by_message = list_citations_for_messages(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=row.conversation.id,
        message_ids=[message.id for message in messages],
    )
    data = ReviewItemDetailRead(
        item=_review_item_response(db, organisation_id=organisation_id, workspace_id=workspace_id, row=row),
        conversation_context=[_message_response(message, citations_by_message.get(message.id, [])) for message in messages],
    )
    return success_response(data.model_dump(mode="json"))


@router.patch("/{workspace_id}/review/unanswered/{assistant_message_id}")
def update_unanswered_review_item(
    workspace_id: str,
    assistant_message_id: str,
    payload: ReviewStatusUpdate,
    db: DbSession,
    current_user: ReviewUpdaterDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        annotation = update_review_status(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            assistant_message_id=assistant_message_id,
            review_status=payload.review_status,
            reviewer_note=payload.reviewer_note,
            actor_user_id=current_user.user_id,
        )
    except InvalidReviewStatus as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ReviewItemNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found for workspace.") from exc

    row = get_review_item_detail(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        assistant_message_id=annotation.assistant_message_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found for workspace.")
    data = _review_item_response(db, organisation_id=organisation_id, workspace_id=workspace_id, row=row)
    return success_response(data.model_dump(mode="json"))


def _ensure_workspace(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


def _validate_filters(*, answer_state: str | None, review_status: str | None) -> None:
    if answer_state is not None and answer_state not in REVIEW_ANSWER_STATES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported review answer_state filter.")
    if review_status is not None and review_status not in REVIEW_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported review_status filter.")


def _review_item_response(db: DbSession, *, organisation_id: str, workspace_id: str, row) -> ReviewItemRead:
    citations = list_citations_for_review_item(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=row.conversation.id,
        assistant_message_id=row.assistant_message.id,
    )
    return ReviewItemRead(
        conversation_id=row.conversation.id,
        assistant_message_id=row.assistant_message.id,
        user_question=row.user_question,
        assistant_answer=row.assistant_message.content,
        answer_state=row.assistant_message.answer_state or "pending",
        error_code=row.assistant_message.error_code,
        channel=row.conversation.channel,
        conversation_status=row.conversation.status,
        model_key=row.assistant_message.model_key,
        provider_key=row.assistant_message.provider_key,
        prompt_key=row.assistant_message.prompt_key,
        prompt_version=row.assistant_message.prompt_version,
        citation_count=row.citation_count,
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
        created_at=row.assistant_message.created_at,
        estimated_cost=row.assistant_message.estimated_cost,
        latency_ms=row.assistant_message.latency_ms,
        review_status=row.review_status,
        reviewer_note=row.reviewer_note,
        reviewed_at=row.reviewed_at,
        reviewed_by=row.reviewed_by,
    )
