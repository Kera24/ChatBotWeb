from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.ai.contracts import AIRequest, AIResponse


class ProviderCapabilities(BaseModel):
    streaming: bool = False
    json_mode: bool = False
    tools: bool = False
    vision: bool = False


class ProviderHealth(BaseModel):
    provider_key: str
    display_name: str
    healthy: bool
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIProvider(ABC):
    provider_key: str
    display_name: str
    capabilities: ProviderCapabilities

    @abstractmethod
    def generate(self, request: AIRequest, *, timeout_seconds: float | None = None) -> AIResponse:
        pass

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key,
            display_name=self.display_name,
            healthy=True,
            status="ok",
            metadata={"capabilities": self.capabilities.model_dump(mode="json")},
        )

    def supports_streaming(self) -> bool:
        return self.capabilities.streaming
