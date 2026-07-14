from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AccessPolicyProfile:
    policy_key: str
    max_request_bytes: int
    max_message_characters: int
    session_lifetime_seconds: int
    max_messages_per_session: int
    retrieval_limit: int
    max_context_characters: int
    max_output_tokens: int
    request_timeout_seconds: int
    origin_required: bool
    fail_closed_on_rate_limit_store_failure: bool
    allowed_model_keys: tuple[str, ...]
    retention_days: int

    def __post_init__(self) -> None:
        if not self.policy_key:
            raise ValueError("Policy key is required.")
        numeric = [
            self.max_request_bytes,
            self.max_message_characters,
            self.session_lifetime_seconds,
            self.max_messages_per_session,
            self.retrieval_limit,
            self.max_context_characters,
            self.max_output_tokens,
            self.request_timeout_seconds,
            self.retention_days,
        ]
        if any(value < 0 for value in numeric):
            raise ValueError("Policy limits must be non-negative.")
        if self.max_request_bytes == 0 or self.max_message_characters == 0 or self.request_timeout_seconds == 0:
            raise ValueError("Core policy limits must be positive.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def internal_test_policy() -> AccessPolicyProfile:
    return AccessPolicyProfile(
        policy_key="internal_test",
        max_request_bytes=4096,
        max_message_characters=500,
        session_lifetime_seconds=3600,
        max_messages_per_session=10,
        retrieval_limit=3,
        max_context_characters=4000,
        max_output_tokens=300,
        request_timeout_seconds=10,
        origin_required=False,
        fail_closed_on_rate_limit_store_failure=True,
        allowed_model_keys=("mock-grounded-answer",),
        retention_days=7,
    )


def planned_widget_policy() -> AccessPolicyProfile:
    return AccessPolicyProfile(
        policy_key="widget",
        max_request_bytes=16384,
        max_message_characters=2000,
        session_lifetime_seconds=86400,
        max_messages_per_session=30,
        retrieval_limit=5,
        max_context_characters=12000,
        max_output_tokens=700,
        request_timeout_seconds=20,
        origin_required=True,
        fail_closed_on_rate_limit_store_failure=True,
        allowed_model_keys=("mock-grounded-answer",),
        retention_days=30,
    )


def planned_partner_api_policy() -> AccessPolicyProfile:
    return AccessPolicyProfile(
        policy_key="partner_api",
        max_request_bytes=32768,
        max_message_characters=4000,
        session_lifetime_seconds=0,
        max_messages_per_session=0,
        retrieval_limit=8,
        max_context_characters=16000,
        max_output_tokens=900,
        request_timeout_seconds=30,
        origin_required=False,
        fail_closed_on_rate_limit_store_failure=True,
        allowed_model_keys=("mock-grounded-answer",),
        retention_days=30,
    )
