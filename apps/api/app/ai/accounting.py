from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.ai.contracts import AIRequest, AIResponse, FinishReason, TokenUsage
from app.ai.model_registry import ModelConfig


class AIExecutionOutcome(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AIUsageRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    created_at: datetime
    organisation_id: str | None = None
    workspace_id: str | None = None
    provider_key: str
    model_key: str
    provider_model_name: str
    prompt_key: str
    prompt_version: str
    prompt_hash: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_input_cost: Decimal = Decimal("0")
    estimated_output_cost: Decimal = Decimal("0")
    total_estimated_cost: Decimal = Decimal("0")
    latency_ms: int = 0
    finish_reason: FinishReason
    outcome: AIExecutionOutcome
    attempt_count: int = 1
    final_attempt_number: int = 1
    retry_performed: bool = False
    timeout_seconds: float | None = None
    provider_health_at_start: str | None = None
    provider_health_at_end: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIUsageAccountingRepository:
    def __init__(self) -> None:
        self._records: list[AIUsageRecord] = []
        self._execution_ids: set[str] = set()

    def add(self, record: AIUsageRecord) -> AIUsageRecord:
        if record.execution_id in self._execution_ids:
            raise ValueError(f"AI usage execution already recorded: {record.execution_id}")
        self._records.append(record)
        self._execution_ids.add(record.execution_id)
        return record

    def list_recent(self, *, limit: int = 50) -> list[AIUsageRecord]:
        safe_limit = max(1, min(limit, 500))
        return list(reversed(self._records[-safe_limit:]))


class AIUsageAccountingService:
    def __init__(self, repository: AIUsageAccountingRepository) -> None:
        self.repository = repository

    def create_execution_id(self) -> str:
        return str(uuid4())

    def record_success(
        self,
        *,
        execution_id: str,
        request: AIRequest,
        response: AIResponse,
        model: ModelConfig,
        attempt_count: int = 1,
        final_attempt_number: int = 1,
        retry_performed: bool = False,
        timeout_seconds: float | None = None,
        provider_health_at_start: str | None = None,
        provider_health_at_end: str | None = None,
    ) -> AIUsageRecord:
        costs = self._calculate_costs(response.token_usage, model)
        return self.repository.add(
            AIUsageRecord(
                execution_id=execution_id,
                created_at=datetime.now(UTC),
                organisation_id=request.organisation_id,
                workspace_id=request.workspace_id,
                provider_key=response.provider_key,
                model_key=response.model_key,
                provider_model_name=response.provider_model_name,
                prompt_key=response.prompt_key,
                prompt_version=response.prompt_version,
                prompt_hash=response.prompt_hash,
                prompt_tokens=response.token_usage.input_tokens,
                completion_tokens=response.token_usage.output_tokens,
                total_tokens=response.token_usage.total_tokens,
                estimated_input_cost=costs[0],
                estimated_output_cost=costs[1],
                total_estimated_cost=costs[2],
                latency_ms=response.latency_ms,
                finish_reason=response.finish_reason,
                outcome=AIExecutionOutcome.SUCCESS,
                attempt_count=attempt_count,
                final_attempt_number=final_attempt_number,
                retry_performed=retry_performed,
                timeout_seconds=timeout_seconds,
                provider_health_at_start=provider_health_at_start,
                provider_health_at_end=provider_health_at_end,
                metadata={"token_usage_estimated": response.token_usage.estimated},
            )
        )

    def record_failure(
        self,
        *,
        execution_id: str,
        request: AIRequest,
        model: ModelConfig,
        latency_ms: int,
        outcome: AIExecutionOutcome,
        finish_reason: FinishReason,
        error_code: str,
        error_message: str,
        attempt_count: int = 1,
        final_attempt_number: int = 1,
        retry_performed: bool = False,
        timeout_seconds: float | None = None,
        provider_health_at_start: str | None = None,
        provider_health_at_end: str | None = None,
    ) -> AIUsageRecord:
        input_tokens = self._estimate_request_tokens(request)
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=0,
            total_tokens=input_tokens,
            estimated=True,
        )
        costs = self._calculate_costs(usage, model)
        return self.repository.add(
            AIUsageRecord(
                execution_id=execution_id,
                created_at=datetime.now(UTC),
                organisation_id=request.organisation_id,
                workspace_id=request.workspace_id,
                provider_key=request.provider_key,
                model_key=request.model_key,
                provider_model_name=request.provider_model_name,
                prompt_key=request.prompt_key,
                prompt_version=request.prompt_version,
                prompt_hash=request.prompt_hash,
                prompt_tokens=usage.input_tokens,
                completion_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                estimated_input_cost=costs[0],
                estimated_output_cost=costs[1],
                total_estimated_cost=costs[2],
                latency_ms=latency_ms,
                finish_reason=finish_reason,
                outcome=outcome,
                attempt_count=attempt_count,
                final_attempt_number=final_attempt_number,
                retry_performed=retry_performed,
                timeout_seconds=timeout_seconds,
                provider_health_at_start=provider_health_at_start,
                provider_health_at_end=provider_health_at_end,
                error_code=error_code,
                error_message=error_message,
                metadata={"token_usage_estimated": True},
            )
        )

    def list_recent(self, *, limit: int = 50) -> list[AIUsageRecord]:
        return self.repository.list_recent(limit=limit)

    @staticmethod
    def _calculate_costs(usage: TokenUsage, model: ModelConfig) -> tuple[Decimal, Decimal, Decimal]:
        input_rate = _rate_to_decimal(model.input_cost_per_million_tokens)
        output_rate = _rate_to_decimal(model.output_cost_per_million_tokens)
        input_cost = (Decimal(usage.input_tokens) / Decimal(1_000_000)) * input_rate
        output_cost = (Decimal(usage.output_tokens) / Decimal(1_000_000)) * output_rate
        return input_cost, output_cost, input_cost + output_cost

    @staticmethod
    def _estimate_request_tokens(request: AIRequest) -> int:
        return sum(max(1, len(message.content.split())) if message.content else 0 for message in request.messages)


def _rate_to_decimal(value: Decimal | float | int | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))
