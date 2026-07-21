from __future__ import annotations

import math
import re
from decimal import Decimal, ROUND_HALF_UP

from app.ai.errors import ModelDisabledError, ModelNotFoundError, ProviderNotFoundError
from app.ai.model_registry import ModelConfig, ModelRegistry
from app.access.messages.cost_control.contracts import PublicCostControlRequest, PublicCostDecision, PublicCostPolicy
from app.access.messages.cost_control.usage import PublicUsageRepository, PublicUsageSnapshot

_WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def estimate_tokens(text: str) -> int:
    if not text:
        return 1
    word_piece_estimate = len(_WORD_RE.findall(text))
    char_estimate = math.ceil(len(text.encode("utf-8")) / 4)
    return max(1, word_piece_estimate, char_estimate)


def estimate_context_tokens(max_context_characters: int) -> int:
    return max(1, math.ceil(max_context_characters / 4))


class PublicMessageCostControlService:
    def __init__(self, *, model_registry: ModelRegistry, usage_repository: PublicUsageRepository | None = None) -> None:
        self.model_registry = model_registry
        self.usage_repository = usage_repository

    def evaluate(self, request: PublicCostControlRequest, *, policy: PublicCostPolicy) -> PublicCostDecision:
        if policy.selected_model_key not in policy.allowed_model_keys:
            return self._deny(request, policy, reason_code="model_not_allowed")
        try:
            model = self.model_registry.get(policy.selected_model_key, require_enabled=True)
        except (ModelNotFoundError, ModelDisabledError, ProviderNotFoundError):
            return self._deny(request, policy, reason_code="model_not_allowed")
        if request.estimated_input_tokens > policy.max_message_tokens:
            return self._deny(request, policy, reason_code="message_budget_exceeded", model=model)
        if policy.session_message_cap and request.current_session_message_count > policy.session_message_cap:
            return self._deny(request, policy, reason_code="session_budget_exceeded", model=model)
        context_tokens = estimate_context_tokens(policy.max_context_characters)
        output_tokens = policy.max_output_tokens
        total_tokens = request.estimated_input_tokens + context_tokens + output_tokens
        estimated_cost = self._estimated_cost(model, input_tokens=request.estimated_input_tokens + context_tokens, output_tokens=output_tokens)
        usage = self._usage_snapshot(request)
        if policy.daily_message_quota is not None and usage.daily_message_count is not None and usage.daily_message_count + 1 > policy.daily_message_quota:
            return self._deny(request, policy, reason_code="workspace_message_quota_exceeded", model=model, degraded=usage.degraded)
        if policy.daily_token_quota is not None and usage.daily_token_usage is not None and usage.daily_token_usage + total_tokens > policy.daily_token_quota:
            return self._deny(request, policy, reason_code="workspace_token_quota_exceeded", model=model, degraded=usage.degraded)
        if policy.daily_cost_quota is not None and usage.daily_estimated_cost is not None and usage.daily_estimated_cost + estimated_cost > policy.daily_cost_quota:
            return self._deny(request, policy, reason_code="workspace_cost_quota_exceeded", model=model, degraded=usage.degraded)
        if total_tokens > model.context_window:
            return self._deny(request, policy, reason_code="message_budget_exceeded", model=model, degraded=usage.degraded)
        return PublicCostDecision(
            allowed=True,
            reason_code="allowed",
            retrieval_limit=policy.retrieval_limit,
            max_context_characters=policy.max_context_characters,
            max_output_tokens=policy.max_output_tokens,
            provider_timeout_seconds=policy.provider_timeout_seconds,
            estimated_input_tokens=request.estimated_input_tokens,
            estimated_max_context_tokens=context_tokens,
            estimated_max_output_tokens=output_tokens,
            estimated_max_total_tokens=total_tokens,
            estimated_max_cost=estimated_cost,
            degraded=usage.degraded,
            safe_metadata={"token_band": self._token_band(total_tokens), "cost_band": self._cost_band(estimated_cost)},
        )

    def _usage_snapshot(self, request: PublicCostControlRequest) -> PublicUsageSnapshot:
        if self.usage_repository is None:
            return PublicUsageSnapshot(
                daily_message_count=request.current_daily_message_count,
                daily_token_usage=request.current_daily_token_usage,
                daily_estimated_cost=request.current_daily_estimated_cost,
            )
        return self.usage_repository.snapshot_for_workspace(organisation_id=request.organisation_id, workspace_id=request.workspace_id, day=request.received_at.date())

    def _deny(self, request: PublicCostControlRequest, policy: PublicCostPolicy, *, reason_code: str, model: ModelConfig | None = None, degraded: bool = False) -> PublicCostDecision:
        context_tokens = estimate_context_tokens(policy.max_context_characters)
        output_tokens = policy.max_output_tokens
        total_tokens = request.estimated_input_tokens + context_tokens + output_tokens
        estimated_cost = self._estimated_cost(model, input_tokens=request.estimated_input_tokens + context_tokens, output_tokens=output_tokens) if model else Decimal("0")
        return PublicCostDecision(
            allowed=False,
            reason_code=reason_code,  # type: ignore[arg-type]
            retrieval_limit=0,
            max_context_characters=0,
            max_output_tokens=0,
            provider_timeout_seconds=0,
            estimated_input_tokens=request.estimated_input_tokens,
            estimated_max_context_tokens=context_tokens,
            estimated_max_output_tokens=output_tokens,
            estimated_max_total_tokens=total_tokens,
            estimated_max_cost=estimated_cost,
            degraded=degraded,
            safe_metadata={"token_band": self._token_band(total_tokens)},
        )

    @staticmethod
    def _estimated_cost(model: ModelConfig | None, *, input_tokens: int, output_tokens: int) -> Decimal:
        if model is None:
            return Decimal("0")
        input_rate = model.input_cost_per_million_tokens or Decimal("0")
        output_rate = model.output_cost_per_million_tokens or Decimal("0")
        cost = (Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / Decimal(1_000_000)
        return cost.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _token_band(tokens: int) -> str:
        if tokens < 1000:
            return "lt_1k"
        if tokens < 5000:
            return "lt_5k"
        if tokens < 10000:
            return "lt_10k"
        return "gte_10k"

    @staticmethod
    def _cost_band(cost: Decimal) -> str:
        if cost == 0:
            return "zero"
        if cost < Decimal("0.001"):
            return "lt_0_001"
        if cost < Decimal("0.01"):
            return "lt_0_01"
        return "gte_0_01"
