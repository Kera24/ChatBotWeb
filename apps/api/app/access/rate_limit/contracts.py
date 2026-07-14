from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

RATE_LIMIT_DIMENSIONS = {"global", "channel", "credential", "workspace", "organisation", "ip", "session", "endpoint_category"}
RATE_LIMIT_CATEGORIES = {"widget_config_read", "widget_session_create", "widget_message_send", "partner_api_request", "internal_test"}
FAIL_MODES = {"fail_closed", "constrained_fail_open", "local_degraded"}


@dataclass(frozen=True)
class RateLimitRule:
    rule_key: str
    category: str
    dimension: str
    capacity: int
    refill_tokens: int
    refill_period_seconds: int
    request_cost: int = 1
    enabled: bool = True
    fail_mode: str = "fail_closed"
    priority: int = 100
    retry_after_cap_seconds: int = 300

    def __post_init__(self) -> None:
        if not self.rule_key:
            raise ValueError("Rate-limit rule key is required.")
        if self.category not in RATE_LIMIT_CATEGORIES:
            raise ValueError("Unsupported rate-limit category.")
        if self.dimension not in RATE_LIMIT_DIMENSIONS:
            raise ValueError("Unsupported rate-limit dimension.")
        if self.fail_mode not in FAIL_MODES:
            raise ValueError("Unsupported rate-limit fail mode.")
        for value in (self.capacity, self.refill_tokens, self.refill_period_seconds, self.request_cost):
            if value <= 0:
                raise ValueError("Rate-limit capacity, refill, period, and cost must be positive.")
        if self.retry_after_cap_seconds < 0:
            raise ValueError("Retry-after cap must be non-negative.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RateLimitRequest:
    request_id: str
    trace_id: str
    environment: str
    channel: str
    category: str
    credential_id: str
    organisation_id: str
    workspace_id: str
    policy_profile: object
    request_cost: int = 1
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    client_ip_identity: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.category not in RATE_LIMIT_CATEGORIES:
            raise ValueError("Unsupported rate-limit category.")
        for value in (self.request_id, self.trace_id, self.environment, self.channel, self.credential_id, self.organisation_id, self.workspace_id):
            if not value:
                raise ValueError("Rate-limit request identifiers are required.")
        if self.request_cost <= 0:
            raise ValueError("Rate-limit request cost must be positive.")

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["received_at"] = self.received_at.isoformat()
        data["policy_profile"] = getattr(self.policy_profile, "policy_key", str(self.policy_profile))
        return data


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    reason_code: str
    limiting_dimension: str | None = None
    rule_key: str | None = None
    limit: int | None = None
    remaining: int | None = None
    retry_after_seconds: int | None = None
    reset_at: datetime | None = None
    degraded: bool = False
    safe_metadata: dict[str, str | int | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if self.reset_at is not None:
            data["reset_at"] = self.reset_at.isoformat()
        return {key: value for key, value in data.items() if value is not None}
