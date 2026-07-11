from typing import Any

from pydantic import BaseModel, Field

from app.ai.contracts import FinishReason, TokenUsage


class AIGenerateRequest(BaseModel):
    prompt_key: str = Field(default="grounded_rag_answer", min_length=1, max_length=120)
    model_key: str = Field(default="mock-grounded-answer", min_length=1, max_length=120)
    variables: dict[str, Any]
    simulate_failure: bool = False
    simulate_timeout: bool = False


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
