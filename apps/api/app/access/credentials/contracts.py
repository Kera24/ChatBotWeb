from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

VALID_CREDENTIAL_TYPES = {"widget_public_key", "partner_api_key", "channel_installation", "future_webhook"}
VALID_CREDENTIAL_STATUSES = {"draft", "active", "disabled", "revoked", "expired"}
VALID_ENVIRONMENTS = {"development", "staging", "production"}


@dataclass(frozen=True)
class CredentialRecord:
    credential_id: str
    organisation_id: str
    workspace_id: str
    credential_type: str
    public_identifier: str
    status: str
    environment: str
    allowed_origins: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    policy_profile: str = "internal_test"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    secret_hash: str | None = None
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.credential_type not in VALID_CREDENTIAL_TYPES:
            raise ValueError("Unsupported credential type.")
        if self.status not in VALID_CREDENTIAL_STATUSES:
            raise ValueError("Unsupported credential status.")
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError("Unsupported credential environment.")
        for required in (self.credential_id, self.organisation_id, self.workspace_id, self.public_identifier, self.policy_profile):
            if not required:
                raise ValueError("Credential records require stable identifiers.")

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at <= (now or datetime.now(timezone.utc))

    def public_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("secret_hash", None)
        for key in ("created_at", "rotated_at", "revoked_at", "expires_at"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data
