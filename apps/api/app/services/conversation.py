from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession, Citation
from app.repositories import conversation_repository as repository


class InvalidConversationStatusTransition(ValueError):
    pass


class InvalidConversationRole(ValueError):
    pass


class InvalidAnswerState(ValueError):
    pass


VALID_CHANNELS = {"dashboard_test", "widget", "api", "future_integration"}
VALID_ROLES = {"system", "user", "assistant", "tool"}
VALID_ANSWER_STATES = {"answered", "low_confidence", "fallback", "failed", "pending"}
CONVERSATION_TRANSITIONS: dict[str, set[str]] = {
    "active": {"completed", "abandoned", "archived"},
    "completed": {"archived"},
    "abandoned": {"archived"},
    "archived": set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_status_transition(current_status: str, new_status: str) -> None:
    if new_status not in CONVERSATION_TRANSITIONS.get(current_status, set()):
        raise InvalidConversationStatusTransition(
            f"Invalid conversation status transition from {current_status!r} to {new_status!r}."
        )


def _validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise InvalidConversationRole(f"Unsupported message role {role!r}.")


def _validate_answer_state(answer_state: str | None) -> None:
    if answer_state is not None and answer_state not in VALID_ANSWER_STATES:
        raise InvalidAnswerState(f"Unsupported answer state {answer_state!r}.")


def start_conversation(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    channel: str,
    anonymous_user_id: str | None = None,
    external_user_id: str | None = None,
    title: str | None = None,
    metadata_json: dict | None = None,
) -> ChatSession:
    if channel not in VALID_CHANNELS:
        raise ValueError(f"Unsupported conversation channel {channel!r}.")
    return repository.create_conversation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        channel=channel,
        anonymous_user_id=anonymous_user_id,
        external_user_id=external_user_id,
        title=title,
        metadata_json=metadata_json,
        started_at=_now(),
    )


def append_user_message(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    content: str,
    metadata_json: dict | None = None,
) -> ChatMessage:
    return _append_message(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        role="user",
        content=content,
        metadata_json=metadata_json,
    )


def append_assistant_message(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    content: str,
    answer_state: str = "answered",
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
    _validate_answer_state(answer_state)
    return _append_message(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        role="assistant",
        content=content,
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
    )


def _append_message(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    role: str,
    content: str,
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
    _validate_role(role)
    conversation = repository.get_conversation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise repository.ConversationNotFound("Conversation not found for tenant workspace.")
    sequence_number = repository.next_sequence_number(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
    )
    return repository.create_message(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        sequence_number=sequence_number,
        created_at=_now(),
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
    )


def mark_conversation_completed(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
) -> ChatSession:
    return _transition_conversation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        status="completed",
        ended_at=_now(),
    )


def archive_conversation(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
) -> ChatSession:
    return _transition_conversation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        status="archived",
        ended_at=_now(),
    )


def _transition_conversation(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    status: str,
    ended_at: datetime,
) -> ChatSession:
    conversation = repository.get_conversation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
    )
    if conversation is None:
        raise repository.ConversationNotFound("Conversation not found for tenant workspace.")
    _validate_status_transition(conversation.status, status)
    return repository.update_conversation_status(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        status=status,
        ended_at=ended_at,
    )


def attach_citations_to_assistant_message(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    conversation_id: str,
    message_id: str,
    citations: list[dict],
) -> list[Citation]:
    return repository.create_citations(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        message_id=message_id,
        citations=citations,
        created_at=_now(),
    )
