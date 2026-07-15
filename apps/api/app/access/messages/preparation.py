from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.errors import PublicAccessError, raise_public_error
from app.access.messages.contracts import IdempotencyResolution, PreparedPublicMessage, PublicMessageInput, PublicMessagePreparationResult
from app.access.messages.idempotency import PublicMessageIdempotencyService, canonical_request_hash
from app.access.messages.validation import normalise_message, validate_message_metadata
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.sessions.contracts import ValidatePublicSessionCommand, ValidatedPublicSessionContext
from app.access.sessions.service import PublicSessionService
from app.db.models import ChatSession


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PublicMessagePreparationService:
    """Internal preparation boundary for future public widget message execution."""

    def __init__(
        self,
        *,
        db: Session,
        public_session_service: PublicSessionService,
        idempotency_service: PublicMessageIdempotencyService | None = None,
        event_sink: InMemoryAccessEventSink | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        self.db = db
        self.public_session_service = public_session_service
        self.idempotency_service = idempotency_service or PublicMessageIdempotencyService(db=db)
        self.event_sink = event_sink or InMemoryAccessEventSink()
        self.clock = clock

    def prepare(
        self,
        command: PublicMessageInput,
        *,
        organisation_id: str,
        workspace_id: str,
        credential_id: str,
        channel: str,
        environment: str,
        policy_profile: str,
        canonical_origin: str | None,
        max_messages: int,
        inactivity_timeout_seconds: int,
    ) -> PublicMessagePreparationResult:
        now = self.clock()
        self._emit("widget.message.preparation_started", command, outcome="started", channel=channel)
        record_id: str | None = None
        processing_owned = False
        try:
            canonical_message = normalise_message(command.message)
            metadata = validate_message_metadata(command.metadata)
            session_context = self.public_session_service.validate_session(
                ValidatePublicSessionCommand(
                    public_session_token=command.session_token,
                    organisation_id=organisation_id,
                    workspace_id=workspace_id,
                    credential_id=credential_id,
                    channel=channel,
                    environment=environment,
                    policy_profile=policy_profile,
                    canonical_origin=canonical_origin,
                    received_at=command.received_at,
                    request_id=command.request_id,
                    trace_id=command.trace_id,
                ),
                max_messages=max_messages,
                inactivity_timeout_seconds=inactivity_timeout_seconds,
            )
            request_hash = canonical_request_hash(
                canonical_message=canonical_message,
                metadata=metadata,
                public_session_id=session_context.internal_session_id,
            )
            idempotency = self.idempotency_service.begin_request(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                credential_id=credential_id,
                public_session_id=session_context.internal_session_id,
                idempotency_key=command.idempotency_key,
                request_hash=request_hash,
                metadata={"client_request_id": command.client_request_id} if command.client_request_id else {},
                now=now,
            )
            record_id = idempotency.record_id
            if idempotency.state != "new":
                self._emit_duplicate(command, idempotency, channel=channel)
                return PublicMessagePreparationResult(idempotency=idempotency)

            processing = self.idempotency_service.mark_processing(
                record_id=record_id or "",
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                now=now,
            )
            if processing.state != "new":
                self._emit_duplicate(command, processing, channel=channel)
                return PublicMessagePreparationResult(idempotency=processing)
            processing_owned = True

            conversation_id = self._resolve_or_create_conversation(session_context, command=command)
            consumed = self.public_session_service.consume_message_slot(
                session_context,
                max_messages=max_messages,
                inactivity_timeout_seconds=inactivity_timeout_seconds,
            )
            self._emit("widget.message.slot_consumed", command, outcome="consumed", channel=channel)
            prepared = PreparedPublicMessage(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                credential_id=credential_id,
                public_session_id=session_context.internal_session_id,
                conversation_id=conversation_id,
                idempotency_record_id=record_id or "",
                canonical_message=canonical_message,
                request_hash=request_hash,
                remaining_messages=consumed.remaining_messages,
                policy_profile=policy_profile,
                channel=channel,
                environment=environment,
                request_id=command.request_id,
                trace_id=command.trace_id,
            )
            self._emit("widget.message.preparation_completed", command, outcome="completed", channel=channel)
            return PublicMessagePreparationResult(
                idempotency=IdempotencyResolution(state="new", record_id=record_id),
                prepared=prepared,
            )
        except PublicAccessError as exc:
            self._emit("widget.message.preparation_failed", command, outcome="failed", channel=channel, error_code=exc.code)
            if processing_owned and record_id:
                self.idempotency_service.mark_failed(
                    record_id=record_id,
                    organisation_id=organisation_id,
                    workspace_id=workspace_id,
                    error_code=exc.code,
                    now=self.clock(),
                )
            raise
        except Exception:
            self._emit("widget.message.preparation_failed", command, outcome="failed", channel=channel, error_code="safe_internal_error")
            if processing_owned and record_id:
                self.idempotency_service.mark_failed(
                    record_id=record_id,
                    organisation_id=organisation_id,
                    workspace_id=workspace_id,
                    error_code="safe_internal_error",
                    now=self.clock(),
                )
            raise_public_error("safe_internal_error")

    def _resolve_or_create_conversation(self, session_context: ValidatedPublicSessionContext, *, command: PublicMessageInput) -> str:
        if session_context.conversation_id:
            conversation = self._load_conversation(session_context, session_context.conversation_id)
            if conversation is None:
                raise_public_error("temporarily_unavailable")
            return conversation.id

        now = self.clock()
        conversation = ChatSession(
            organisation_id=session_context.organisation_id,
            workspace_id=session_context.workspace_id,
            channel="widget",
            status="active",
            title=None,
            metadata_json={"created_by": "public_message_preparation"},
            started_at=now,
        )
        self.db.add(conversation)
        self.db.flush()
        self._emit("widget.message.conversation_created", command, outcome="created", channel=session_context.channel)
        attached_id = self.public_session_service.attach_conversation(session_context, conversation_id=conversation.id)
        if attached_id != conversation.id:
            self.db.delete(conversation)
            self.db.flush()
            attached = self._load_conversation(session_context, attached_id)
            if attached is None:
                raise_public_error("temporarily_unavailable")
        self._emit("widget.message.conversation_attached", command, outcome="attached", channel=session_context.channel)
        return attached_id

    def _load_conversation(self, session_context: ValidatedPublicSessionContext, conversation_id: str) -> ChatSession | None:
        statement = select(ChatSession).where(
            ChatSession.id == conversation_id,
            ChatSession.organisation_id == session_context.organisation_id,
            ChatSession.workspace_id == session_context.workspace_id,
            ChatSession.status == "active",
        )
        return self.db.execute(statement).scalar_one_or_none()

    def _emit_duplicate(self, command: PublicMessageInput, resolution: IdempotencyResolution, *, channel: str) -> None:
        if resolution.state == "completed":
            event_type = "widget.message.idempotency_duplicate"
            error_code = None
        elif resolution.state == "conflict":
            event_type = "widget.message.idempotency_conflict"
            error_code = "idempotency_conflict"
        elif resolution.state == "processing":
            event_type = "widget.message.request_in_progress"
            error_code = "request_in_progress"
        else:
            event_type = "widget.message.idempotency_duplicate"
            error_code = resolution.safe_error_code
        self._emit(event_type, command, outcome=resolution.state, channel=channel, error_code=error_code)

    def _emit(
        self,
        event_type: str,
        command: PublicMessageInput,
        *,
        outcome: str,
        channel: str,
        error_code: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.event_sink.emit(
            AccessEvent(
                event_type=event_type,
                request_id=command.request_id,
                trace_id=command.trace_id,
                channel=channel,
                outcome=outcome,
                error_code=error_code,
            )
        )

