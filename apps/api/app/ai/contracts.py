from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALL = "tool_call"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    TIMEOUT = "timeout"


class AIMessage(BaseModel):
    role: MessageRole
    content: str
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = True


class ProviderMetadata(BaseModel):
    provider_key: str
    provider_model_name: str
    response_id: str | None = None
    raw_finish_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    organisation_id: str | None = None
    workspace_id: str | None = None
    provider_key: str
    model_key: str
    provider_model_name: str
    prompt_key: str
    prompt_version: str
    prompt_hash: str
    messages: list[AIMessage]
    temperature: float = 0.0
    max_output_tokens: int = 512
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIResponse(BaseModel):
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
    provider_metadata: ProviderMetadata
    metadata: dict[str, Any] = Field(default_factory=dict)
