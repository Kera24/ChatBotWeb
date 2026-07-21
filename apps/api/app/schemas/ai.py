from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.ai.accounting import AIExecutionOutcome
from app.ai.contracts import FinishReason, TokenUsage
from app.ai.health import ProviderHealthStatus
from app.ai.providers.base import ProviderCapabilities


class AIGenerateRequest(BaseModel):
    prompt_key: str = Field(default="grounded_rag_answer", min_length=1, max_length=120)
    model_key: str = Field(default="mock-grounded-answer", min_length=1, max_length=120)
    variables: dict[str, Any]
    simulate_failure: bool = False
    simulate_timeout: bool = False
    simulate_transient_failures: int = Field(default=0, ge=0, le=4)


class AIGenerateResponse(BaseModel):
    text: str
    provider_key: str
    model_key: str
    provider_model_name: str
    prompt_key: str
    prompt_version: str
    prompt_hash: str
    token_usage: TokenUsage
    latency_ms: int
    finish_reason: FinishReason


class AIUsageRecordResponse(BaseModel):
    execution_id: str
    created_at: str
    organisation_id: str | None = None
    workspace_id: str | None = None
    provider_key: str
    model_key: str
    provider_model_name: str
    prompt_key: str
    prompt_version: str
    prompt_hash: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_input_cost: Decimal
    estimated_output_cost: Decimal
    total_estimated_cost: Decimal
    latency_ms: int
    finish_reason: FinishReason
    outcome: AIExecutionOutcome
    attempt_count: int
    final_attempt_number: int
    retry_performed: bool
    timeout_seconds: float | None = None
    provider_health_at_start: str | None = None
    provider_health_at_end: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class AIProviderHealthResponse(BaseModel):
    provider_key: str
    status: ProviderHealthStatus
    checked_at: str
    latency_ms: int | None = None
    message: str | None = None
    consecutive_failures: int
    last_success_at: str | None = None
    last_failure_at: str | None = None


class AIProviderModelResponse(BaseModel):
    model_key: str
    provider_model_name: str
    display_name: str
    enabled: bool


class AIProviderResponse(BaseModel):
    provider_key: str
    display_name: str
    capabilities: ProviderCapabilities
    current_health: AIProviderHealthResponse
    registered_models: list[AIProviderModelResponse]
