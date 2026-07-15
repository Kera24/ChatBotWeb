from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

SAFE_EVENT_TYPES = {
    "access.request.received",
    "access.channel.resolved",
    "access.credential.resolved",
    "access.credential.invalid",
    "access.tenant.resolved",
    "access.request.rejected",
    "access.request.validated",
    "origin.validation.allowed",
    "origin.validation.denied",
    "origin.validation.missing",
    "origin.validation.malformed",
    "origin.validation.wildcard_matched",
    "origin.validation.development_exception",
    "rate_limit.allowed",
    "rate_limit.denied",
    "rate_limit.redis_unavailable",
    "rate_limit.redis_timeout",
    "rate_limit.degraded_local_fallback",
    "rate_limit.invalid_policy",
    "rate_limit.emergency_mode",
    "public_session.created",
    "public_session.validated",
    "public_session.expired",
    "public_session.rejected",
    "public_session.revoked",
    "public_session.blocked",
    "public_session.completed",
    "public_session.origin_mismatch",
    "public_session.message_limit_reached",
    "public_session.conversation_attached",
    "public_session.credential_invalidated",
    "widget.session.requested",
    "widget.session.created",
    "widget.session.rejected",
    "widget.session.rate_limited",
    "widget.session.origin_denied",
    "widget.session.unavailable",
    "widget.config.requested",
    "widget.config.served",
    "widget.config.not_modified",
    "widget.config.rejected",
    "widget.config.origin_denied",
    "widget.config.rate_limited",
    "widget.config.unavailable",
    "widget.config.asset_omitted",
    "widget.config.degraded_rate_limit",
    "widget.message.preparation_started",
    "widget.message.validation_rejected",
    "widget.message.idempotency_new",
    "widget.message.idempotency_duplicate",
    "widget.message.idempotency_conflict",
    "widget.message.request_in_progress",
    "widget.message.slot_consumed",
    "widget.message.conversation_created",
    "widget.message.conversation_attached",
    "widget.message.preparation_completed",
    "widget.message.preparation_failed",
    "widget.message.abuse_check_started",
    "widget.message.abuse_allowed",
    "widget.message.abuse_restricted",
    "widget.message.abuse_rejected",
    "widget.message.session_blocked",
    "widget.message.cost_check_started",
    "widget.message.cost_allowed",
    "widget.message.quota_denied",
    "widget.message.cost_policy_invalid",
    "widget.message.security_preparation_completed",
    "widget.message.security_preparation_failed",
    "widget.message.requested",
    "widget.message.accepted",
    "widget.message.rejected",
    "widget.message.rate_limited",
    "widget.message.origin_denied",
    "widget.message.rag_started",
    "widget.message.rag_completed",
    "widget.message.rag_failed",
    "widget.message.fallback",
    "widget.message.duplicate",
    "widget.message.response_projected",
}


@dataclass(frozen=True)
class AccessEvent:
    event_type: str
    request_id: str
    trace_id: str
    channel: str | None = None
    credential_id: str | None = None
    outcome: str | None = None
    error_code: str | None = None
    latency_ms: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.event_type not in SAFE_EVENT_TYPES:
            raise ValueError("Unsupported access event type.")

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return {key: value for key, value in data.items() if value is not None}


class InMemoryAccessEventSink:
    def __init__(self) -> None:
        self.events: list[AccessEvent] = []

    def emit(self, event: AccessEvent) -> None:
        self.events.append(event)
