from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.access.contracts import validate_metadata

PUBLIC_SESSION_STATUSES = {"active", "completed", "expired", "revoked", "blocked"}
PUBLIC_SESSION_TERMINAL_STATUSES = {"completed", "expired", "revoked", "blocked"}


@dataclass(frozen=True)
class CreatePublicSessionCommand:
    organisation_id: str
    workspace_id: str
    credential_id: str
    channel: str
    environment: str
    policy_profile: str
    inactivity_timeout_seconds: int
    absolute_lifetime_seconds: int
    max_messages: int
    request_id: str
    trace_id: str
    origin_id: str | None = None
    canonical_origin: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    received_at: datetime | None = None

    def __post_init__(self) -> None:
        for value in (self.organisation_id, self.workspace_id, self.credential_id, self.channel, self.environment, self.policy_profile, self.request_id, self.trace_id):
            if not value:
                raise ValueError("Public session creation requires resolved server-side context.")
        if self.inactivity_timeout_seconds <= 0 or self.absolute_lifetime_seconds <= 0:
            raise ValueError("Public session expiry values must be positive.")
        if self.inactivity_timeout_seconds > self.absolute_lifetime_seconds:
            raise ValueError("Inactivity timeout cannot exceed absolute lifetime.")
        if self.max_messages <= 0:
            raise ValueError("Public sessions require a positive message cap.")
        object.__setattr__(self, "metadata", validate_metadata(dict(self.metadata)))


@dataclass(frozen=True)
class CreatedPublicSession:
    public_session_token: str
    expires_at: datetime
    absolute_expires_at: datetime
    inactivity_timeout_seconds: int
    max_messages: int
    safe_capabilities: tuple[str, ...]
    request_id: str
    trace_id: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["expires_at"] = self.expires_at.isoformat()
        data["absolute_expires_at"] = self.absolute_expires_at.isoformat()
        return data


@dataclass(frozen=True)
class ValidatePublicSessionCommand:
    public_session_token: str
    organisation_id: str
    workspace_id: str
    credential_id: str
    channel: str
    environment: str
    policy_profile: str
    received_at: datetime
    request_id: str
    trace_id: str
    canonical_origin: str | None = None

    def __post_init__(self) -> None:
        for value in (self.public_session_token, self.organisation_id, self.workspace_id, self.credential_id, self.channel, self.environment, self.policy_profile, self.request_id, self.trace_id):
            if not value:
                raise ValueError("Public session validation requires token and resolved context.")


@dataclass(frozen=True)
class ValidatedPublicSessionContext:
    internal_session_id: str
    organisation_id: str
    workspace_id: str
    credential_id: str
    channel: str
    environment: str
    policy_profile: str
    conversation_id: str | None
    message_count: int
    remaining_messages: int
    expires_at: datetime
    absolute_expires_at: datetime
    rate_limit_identity: str
    request_id: str
    trace_id: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["expires_at"] = self.expires_at.isoformat()
        data["absolute_expires_at"] = self.absolute_expires_at.isoformat()
        return data


@dataclass(frozen=True)
class ConsumedMessageSlot:
    internal_session_id: str
    message_count: int
    remaining_messages: int
    request_id: str
    trace_id: str


@dataclass(frozen=True)
class SessionOperationResult:
    internal_session_id: str
    status: str
    request_id: str
    trace_id: str

