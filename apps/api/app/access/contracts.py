from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.access.errors import PublicAccessErrorDetail

MAX_METADATA_ITEMS = 20
MAX_METADATA_KEY_CHARS = 80
MAX_METADATA_VALUE_CHARS = 500
MAX_REQUEST_ID_CHARS = 120
MAX_CHANNEL_KEY_CHARS = 80


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_request_id() -> str:
    return f"access_{uuid4()}"


def validate_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    if len(metadata) > MAX_METADATA_ITEMS:
        raise ValueError("Metadata contains too many items.")
    safe: dict[str, str | int | float | bool | None] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not key or len(key) > MAX_METADATA_KEY_CHARS:
            raise ValueError("Metadata keys must be bounded strings.")
        if isinstance(value, str):
            if len(value) > MAX_METADATA_VALUE_CHARS:
                raise ValueError("Metadata values are too large.")
            safe[key] = value
        elif value is None or isinstance(value, (int, float, bool)):
            safe[key] = value
        else:
            raise ValueError("Metadata values must be scalar and public-safe.")
    return safe


@dataclass(frozen=True)
class PublicCredentialReference:
    credential_type: str
    public_identifier: str

    def __post_init__(self) -> None:
        if not self.credential_type or not self.public_identifier:
            raise ValueError("Credential type and public identifier are required.")
        if len(self.public_identifier) > 256:
            raise ValueError("Credential identifier is too long.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PublicAccessRequest:
    channel: str
    public_credential: PublicCredentialReference
    message: str
    request_id: str = field(default_factory=new_request_id)
    public_session_token: str | None = None
    origin: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    channel_metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    received_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.request_id or len(self.request_id) > MAX_REQUEST_ID_CHARS:
            raise ValueError("A bounded request_id is required.")
        if not self.channel or len(self.channel) > MAX_CHANNEL_KEY_CHARS:
            raise ValueError("A bounded channel key is required.")
        if self.message is None:
            raise ValueError("Message is required.")
        object.__setattr__(self, "channel_metadata", validate_metadata(dict(self.channel_metadata)))

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["received_at"] = self.received_at.isoformat()
        return data


@dataclass(frozen=True)
class CostLimits:
    max_output_tokens: int
    request_timeout_seconds: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class NormalisedAccessContext:
    request_id: str
    trace_id: str
    organisation_id: str
    workspace_id: str
    channel: str
    credential_id: str
    policy_profile: str
    cost_limits: CostLimits
    received_at: datetime
    session_id: str | None = None
    rate_limit_identity: str | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["received_at"] = self.received_at.isoformat()
        return data


@dataclass(frozen=True)
class PublicAccessResponse:
    request_id: str
    trace_id: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    safe_error: PublicAccessErrorDetail | None = None
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", validate_metadata(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "status": self.status,
            "payload": self.payload,
            "safe_error": self.safe_error.to_public_dict() if self.safe_error else None,
            "metadata": self.metadata,
        }
