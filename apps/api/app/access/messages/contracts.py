from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

IdempotencyState = Literal["new", "processing", "completed", "failed", "conflict"]


@dataclass(frozen=True)
class PublicMessageInput:
    session_token: str
    message: str
    idempotency_key: str
    request_id: str
    trace_id: str
    received_at: datetime
    client_request_id: str | None = None
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(frozen=True)
class PreparedPublicMessage:
    organisation_id: str
    workspace_id: str
    credential_id: str
    public_session_id: str
    conversation_id: str
    idempotency_record_id: str
    canonical_message: str
    request_hash: str
    remaining_messages: int
    policy_profile: str
    channel: str
    environment: str
    request_id: str
    trace_id: str


@dataclass(frozen=True)
class IdempotencyResolution:
    state: IdempotencyState
    record_id: str | None = None
    stored_response: dict[str, Any] | None = None
    safe_error_code: str | None = None


@dataclass(frozen=True)
class PublicMessagePreparationResult:
    idempotency: IdempotencyResolution
    prepared: PreparedPublicMessage | None = None
