from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession, Citation, Chunk


class ConversationNotFound(LookupError):
    pass


class MessageNotFound(LookupError):
    pass


class CitationValidationError(ValueError):
    pass


def create_conversation(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    channel: str,
    status: str = "active",
    anonymous_user_id: str | None = None,
    external_user_id: str | None = None,
    title: str | None = None,
    metadata_json: dict | None = None,
    started_at: datetime,
) -> ChatSession:
    conversation = ChatSession(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        channel=channel,
        status=status,
        anonymous_user_id=anonymous_user_id,
        external_user_id=external_user_id,
        title=title,
        metadata_json=metadata_json,
        started_at=started_at,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
) -> ChatSession | None:
    statement = select(ChatSession).where(
        ChatSession.id == conversation_id,
        ChatSession.organisation_id == organisation_id,
        ChatSession.workspace_id == workspace_id,
    )
    return db.execute(statement).scalar_one_or_none()


def list_conversations(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[ChatSession]:
    statement = select(ChatSession).where(
        ChatSession.organisation_id == organisation_id,
        ChatSession.workspace_id == workspace_id,
    )
    if status is not None:
        statement = statement.where(ChatSession.status == status)
    statement = statement.order_by(ChatSession.last_message_at.desc().nullslast(), ChatSession.started_at.desc()).limit(limit)
    return list(db.execute(statement).scalars().all())


def update_conversation_status(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    status: str,
    ended_at: datetime | None = None,
) -> ChatSession:
    conversation = get_conversation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise ConversationNotFound("Conversation not found for tenant workspace.")
    conversation.status = status
    if ended_at is not None:
        conversation.ended_at = ended_at
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def next_sequence_number(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
) -> int:
    statement = select(func.max(ChatMessage.sequence_number)).where(
        ChatMessage.organisation_id == organisation_id,
        ChatMessage.workspace_id == workspace_id,
        ChatMessage.conversation_id == conversation_id,
    )
    current = db.execute(statement).scalar_one()
    return int(current or 0) + 1


def create_message(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    role: str,
    content: str,
    sequence_number: int,
    created_at: datetime,
    answer_state: str | None = None,
    model_key: str | None = None,
    provider_key: str | None = None,
    provider_model_name: str | None = None,
    prompt_key: str | None = None,
    prompt_version: int | None = None,
    prompt_hash: str | None = None,
    execution_id: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost: Decimal | None = None,
    latency_ms: int | None = None,
    finish_reason: str | None = None,
    error_code: str | None = None,
    metadata_json: dict | None = None,
) -> ChatMessage:
    conversation = get_conversation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise ConversationNotFound("Conversation not found for tenant workspace.")
    message = ChatMessage(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence_number=sequence_number,
        answer_state=answer_state,
        model_key=model_key,
        provider_key=provider_key,
        provider_model_name=provider_model_name,
        prompt_key=prompt_key,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        execution_id=execution_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        error_code=error_code,
        metadata_json=metadata_json,
        created_at=created_at,
    )
    conversation.last_message_at = created_at
    db.add(message)
    db.add(conversation)
    db.commit()
    db.refresh(message)
    return message


def list_messages(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
) -> list[ChatMessage]:
    statement = select(ChatMessage).where(
        ChatMessage.organisation_id == organisation_id,
        ChatMessage.workspace_id == workspace_id,
        ChatMessage.conversation_id == conversation_id,
    ).order_by(ChatMessage.sequence_number)
    return list(db.execute(statement).scalars().all())


def get_message(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    message_id: str,
) -> ChatMessage | None:
    statement = select(ChatMessage).where(
        ChatMessage.id == message_id,
        ChatMessage.organisation_id == organisation_id,
        ChatMessage.workspace_id == workspace_id,
        ChatMessage.conversation_id == conversation_id,
    )
    return db.execute(statement).scalar_one_or_none()


def create_citations(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    message_id: str,
    citations: Iterable[dict],
    created_at: datetime,
) -> list[Citation]:
    message = get_message(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    if message is None:
        raise MessageNotFound("Message not found for tenant conversation.")
    if message.role != "assistant":
        raise CitationValidationError("Citations can only be attached to assistant messages.")

    created: list[Citation] = []
    for item in citations:
        chunk_id = item["chunk_id"]
        statement = select(Chunk).where(
            Chunk.id == chunk_id,
            Chunk.organisation_id == organisation_id,
            Chunk.workspace_id == workspace_id,
        )
        chunk = db.execute(statement).scalar_one_or_none()
        if chunk is None:
            raise CitationValidationError("Citation chunk does not exist in tenant workspace.")
        if item.get("document_id", chunk.document_id) != chunk.document_id:
            raise CitationValidationError("Citation document does not match chunk.")
        if item.get("document_version_id", chunk.document_version_id) != chunk.document_version_id:
            raise CitationValidationError("Citation document version does not match chunk.")

        citation = Citation(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            message_id=message_id,
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_version_id=chunk.document_version_id,
            citation_index=item["citation_index"],
            similarity_score=item.get("similarity_score"),
            source_title=item.get("source_title") or chunk.source_title,
            source_type=item.get("source_type") or chunk.source_type,
            page_number=item.get("page_number", chunk.page_number),
            section_title=item.get("section_title", chunk.section_title),
            quoted_text=item.get("quoted_text"),
            metadata_json=item.get("metadata_json"),
            created_at=created_at,
        )
        db.add(citation)
        created.append(citation)

    db.commit()
    for citation in created:
        db.refresh(citation)
    return created


def list_citations_for_message(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    message_id: str,
) -> list[Citation]:
    statement = select(Citation).where(
        Citation.organisation_id == organisation_id,
        Citation.workspace_id == workspace_id,
        Citation.conversation_id == conversation_id,
        Citation.message_id == message_id,
    ).order_by(Citation.citation_index)
    return list(db.execute(statement).scalars().all())
