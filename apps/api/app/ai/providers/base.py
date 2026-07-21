from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.ai.contracts import AIRequest, AIResponse
from app.ai.health import ProviderHealth, ProviderHealthStatus


class ProviderCapabilities(BaseModel):
    streaming: bool = False
    json_mode: bool = False
    tools: bool = False
    vision: bool = False


class AIProvider(ABC):
    provider_key: str
    display_name: str
    capabilities: ProviderCapabilities

    @abstractmethod
    def generate(self, request: AIRequest, *, timeout_seconds: float | None = None) -> AIResponse:
        pass

    def health(self) -> ProviderHealth:
        from datetime import UTC, datetime

        return ProviderHealth(
            provider_key=self.provider_key,
            status=ProviderHealthStatus.HEALTHY,
            checked_at=datetime.now(UTC),
            message="Provider health check succeeded.",
            metadata={"capabilities": self.capabilities.model_dump(mode="json")},
        )

    def supports_streaming(self) -> bool:
        return self.capabilities.streaming
