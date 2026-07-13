from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.orm import Session, aliased

from app.db.models import ChatMessage, ChatSession, Citation, ReviewAnnotation
from app.repositories.audit_repository import add_audit_event

REVIEW_ANSWER_STATES = {"fallback", "failed", "low_confidence"}
REVIEW_STATUSES = {"open", "reviewed", "dismissed", "knowledge_gap"}


class ReviewItemNotFound(LookupError):
    pass


class InvalidReviewStatus(ValueError):
    pass


@dataclass(frozen=True)
class ReviewItemRow:
    conversation: ChatSession
    assistant_message: ChatMessage
    user_question: str | None
    citation_count: int
    review_status: str
    reviewer_note: str | None
    reviewed_at: datetime | None
    reviewed_by: str | None


def list_review_items(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    answer_state: str | None = None,
    review_status: str | None = None,
    channel: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ReviewItemRow]:
    statement = _review_item_select(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        answer_state=answer_state,
        review_status=review_status,
        channel=channel,
        created_after=created_after,
        created_before=created_before,
    )
    statement = statement.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).offset(max(0, offset)).limit(max(1, min(limit, 100)))
    return [_row_to_review_item(row) for row in db.execute(statement).all()]


def count_review_items(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    answer_state: str | None = None,
    review_status: str | None = None,
    channel: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> int:
    base = _review_base_query(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        answer_state=answer_state,
        review_status=review_status,
        channel=channel,
        created_after=created_after,
        created_before=created_before,
    )
    statement = select(func.count(ChatMessage.id)).select_from(ChatMessage).join(ChatSession, ChatSession.id == ChatMessage.conversation_id).outerjoin(
        ReviewAnnotation,
        and_(
            ReviewAnnotation.assistant_message_id == ChatMessage.id,
            ReviewAnnotation.organisation_id == organisation_id,
            ReviewAnnotation.workspace_id == workspace_id,
        ),
    )
    statement = base(statement)
    return int(db.execute(statement).scalar_one() or 0)


def get_review_item_detail(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    assistant_message_id: str,
) -> ReviewItemRow | None:
    statement = _review_item_select(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        assistant_message_id=assistant_message_id,
    )
    row = db.execute(statement).first()
    return _row_to_review_item(row) if row is not None else None


def update_review_status(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    assistant_message_id: str,
    review_status: str,
    reviewer_note: str | None,
    actor_user_id: str | None,
) -> ReviewAnnotation:
    if review_status not in REVIEW_STATUSES:
        raise InvalidReviewStatus(f"Unsupported review status {review_status!r}.")

    item = get_review_item_detail(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        assistant_message_id=assistant_message_id,
    )
    if item is None:
        raise ReviewItemNotFound("Review item not found for tenant workspace.")

    annotation = _get_annotation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        assistant_message_id=assistant_message_id,
    )
    previous_status = annotation.review_status if annotation is not None else "open"
    now = datetime.now(timezone.utc)
    if annotation is None:
        annotation = ReviewAnnotation(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            conversation_id=item.conversation.id,
            assistant_message_id=assistant_message_id,
            review_status=review_status,
        )
    annotation.review_status = review_status
    annotation.reviewer_note = reviewer_note
    annotation.reviewed_at = now
    annotation.reviewed_by = actor_user_id
    db.add(annotation)
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        action="review.status.changed",
        entity_type="chat_message",
        entity_id=assistant_message_id,
        actor_user_id=actor_user_id,
        previous_status=previous_status,
        new_status=review_status,
        metadata_json={"conversation_id": item.conversation.id, "answer_state": item.assistant_message.answer_state},
    )
    db.commit()
    db.refresh(annotation)
    return annotation


def list_citations_for_review_item(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    assistant_message_id: str,
) -> list[Citation]:
    statement = select(Citation).where(
        Citation.organisation_id == organisation_id,
        Citation.workspace_id == workspace_id,
        Citation.conversation_id == conversation_id,
        Citation.message_id == assistant_message_id,
    ).order_by(Citation.citation_index)
    return list(db.execute(statement).scalars().all())


def _review_item_select(
    *,
    organisation_id: str,
    workspace_id: str,
    answer_state: str | None = None,
    review_status: str | None = None,
    channel: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    assistant_message_id: str | None = None,
):
    UserMessage = aliased(ChatMessage)
    user_question = (
        select(UserMessage.content)
        .where(
            UserMessage.organisation_id == organisation_id,
            UserMessage.workspace_id == workspace_id,
            UserMessage.conversation_id == ChatMessage.conversation_id,
            UserMessage.role == "user",
            UserMessage.sequence_number < ChatMessage.sequence_number,
        )
        .order_by(UserMessage.sequence_number.desc())
        .limit(1)
        .correlate(ChatMessage)
        .scalar_subquery()
    )
    citation_count = (
        select(func.count(Citation.id))
        .where(
            Citation.organisation_id == organisation_id,
            Citation.workspace_id == workspace_id,
            Citation.conversation_id == ChatMessage.conversation_id,
            Citation.message_id == ChatMessage.id,
        )
        .correlate(ChatMessage)
        .scalar_subquery()
    )
    review_status_value = func.coalesce(ReviewAnnotation.review_status, literal("open"))

    statement = (
        select(
            ChatSession,
            ChatMessage,
            user_question,
            citation_count,
            review_status_value,
            ReviewAnnotation.reviewer_note,
            ReviewAnnotation.reviewed_at,
            ReviewAnnotation.reviewed_by,
        )
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.conversation_id)
        .outerjoin(
            ReviewAnnotation,
            and_(
                ReviewAnnotation.assistant_message_id == ChatMessage.id,
                ReviewAnnotation.organisation_id == organisation_id,
                ReviewAnnotation.workspace_id == workspace_id,
            ),
        )
    )
    if assistant_message_id is not None:
        statement = statement.where(ChatMessage.id == assistant_message_id)
    return _review_base_query(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        answer_state=answer_state,
        review_status=review_status,
        channel=channel,
        created_after=created_after,
        created_before=created_before,
    )(statement)


def _review_base_query(
    *,
    organisation_id: str,
    workspace_id: str,
    answer_state: str | None = None,
    review_status: str | None = None,
    channel: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
):
    states = [answer_state] if answer_state else sorted(REVIEW_ANSWER_STATES)

    def apply(statement):
        statement = statement.where(
            ChatMessage.organisation_id == organisation_id,
            ChatMessage.workspace_id == workspace_id,
            ChatMessage.role == "assistant",
            ChatMessage.answer_state.in_(states),
            ChatSession.organisation_id == organisation_id,
            ChatSession.workspace_id == workspace_id,
        )
        if review_status is not None:
            if review_status == "open":
                statement = statement.where(or_(ReviewAnnotation.review_status == "open", ReviewAnnotation.id.is_(None)))
            else:
                statement = statement.where(ReviewAnnotation.review_status == review_status)
        if channel is not None:
            statement = statement.where(ChatSession.channel == channel)
        if created_after is not None:
            statement = statement.where(ChatMessage.created_at >= created_after)
        if created_before is not None:
            statement = statement.where(ChatMessage.created_at <= created_before)
        return statement

    return apply


def _get_annotation(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    assistant_message_id: str,
) -> ReviewAnnotation | None:
    statement = select(ReviewAnnotation).where(
        ReviewAnnotation.organisation_id == organisation_id,
        ReviewAnnotation.workspace_id == workspace_id,
        ReviewAnnotation.assistant_message_id == assistant_message_id,
    )
    return db.execute(statement).scalar_one_or_none()


def _row_to_review_item(row) -> ReviewItemRow:
    return ReviewItemRow(
        conversation=row[0],
        assistant_message=row[1],
        user_question=row[2],
        citation_count=int(row[3] or 0),
        review_status=row[4] or "open",
        reviewer_note=row[5],
        reviewed_at=row[6],
        reviewed_by=row[7],
    )
