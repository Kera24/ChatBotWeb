from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

AbuseDecisionStatus = Literal["allow", "allow_with_restrictions", "reject", "block_session"]
AbuseReasonCode = Literal[
    "none",
    "repeated_message",
    "excessive_repetition",
    "excessive_urls",
    "encoded_payload",
    "system_prompt_extraction",
    "instruction_override",
    "cross_tenant_probe",
    "suspicious_automation",
    "unsupported_payload",
    "unsafe_control_pattern",
    "policy_violation",
]


@dataclass(frozen=True)
class AbusePolicy:
    policy_key: str
    max_urls_per_message: int = 6
    max_url_length: int = 400
    repeated_character_threshold: int = 24
    repeated_phrase_threshold: int = 8
    encoded_payload_ratio_threshold: float = 0.72
    repeated_message_window_seconds: int = 900
    repeated_message_limit: int = 2
    suspicious_pattern_action: AbuseDecisionStatus = "reject"
    cross_tenant_probe_action: AbuseDecisionStatus = "reject"
    block_session_after_rejections: int | None = None
    max_rejections_per_session: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AbuseCheckRequest:
    organisation_id: str
    workspace_id: str
    credential_id: str
    public_session_id: str
    conversation_id: str
    canonical_message: str
    message_hash: str
    policy_profile: str
    channel: str
    recent_session_message_fingerprints: tuple[str, ...]
    request_id: str
    trace_id: str
    received_at: datetime

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["received_at"] = self.received_at.isoformat()
        return data


@dataclass(frozen=True)
class AbuseDecision:
    status: AbuseDecisionStatus
    reason_codes: tuple[AbuseReasonCode, ...] = ("none",)
    restriction_profile: str | None = None
    should_block_session: bool = False
    safe_public_error_code: str | None = None
    safe_metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    evaluated_rules: tuple[str, ...] = ()
    decision_version: str = "abuse-rules-v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def allowed(self) -> bool:
        return self.status in {"allow", "allow_with_restrictions"}
