from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

CostReasonCode = Literal[
    "allowed",
    "message_budget_exceeded",
    "session_budget_exceeded",
    "workspace_message_quota_exceeded",
    "workspace_token_quota_exceeded",
    "workspace_cost_quota_exceeded",
    "model_not_allowed",
    "policy_invalid",
    "temporarily_unavailable",
]


@dataclass(frozen=True)
class PublicCostPolicy:
    policy_key: str
    selected_model_key: str
    max_message_tokens: int
    retrieval_limit: int
    max_context_characters: int
    max_output_tokens: int
    provider_timeout_seconds: int
    allowed_model_keys: tuple[str, ...]
    session_message_cap: int
    daily_message_quota: int | None = None
    daily_token_quota: int | None = None
    daily_cost_quota: Decimal | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if self.daily_cost_quota is not None:
            data["daily_cost_quota"] = str(self.daily_cost_quota)
        return data


@dataclass(frozen=True)
class PublicCostControlRequest:
    organisation_id: str
    workspace_id: str
    credential_id: str
    public_session_id: str
    policy_profile: str
    canonical_message: str
    message_character_count: int
    estimated_input_tokens: int
    requested_operation: str
    current_session_message_count: int
    current_daily_message_count: int | None
    current_daily_token_usage: int | None
    current_daily_estimated_cost: Decimal | None
    request_id: str
    trace_id: str
    received_at: datetime

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["received_at"] = self.received_at.isoformat()
        if self.current_daily_estimated_cost is not None:
            data["current_daily_estimated_cost"] = str(self.current_daily_estimated_cost)
        return data


@dataclass(frozen=True)
class PublicCostDecision:
    allowed: bool
    reason_code: CostReasonCode
    retrieval_limit: int
    max_context_characters: int
    max_output_tokens: int
    provider_timeout_seconds: int
    estimated_input_tokens: int
    estimated_max_context_tokens: int
    estimated_max_output_tokens: int
    estimated_max_total_tokens: int
    estimated_max_cost: Decimal
    degraded: bool = False
    safe_metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    decision_version: str = "public-cost-v1"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["estimated_max_cost"] = str(self.estimated_max_cost)
        return data
