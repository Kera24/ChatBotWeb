from __future__ import annotations

from app.ai.errors import ProviderNotFoundError
from app.ai.health import ProviderHealth
from app.ai.providers.base import AIProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}

    def register(self, provider: AIProvider) -> None:
        if provider.provider_key in self._providers:
            raise ValueError(f"Provider already registered: {provider.provider_key}")
        self._providers[provider.provider_key] = provider

    def get(self, provider_key: str) -> AIProvider:
        provider = self._providers.get(provider_key)
        if provider is None:
            raise ProviderNotFoundError(f"Provider not found: {provider_key}")
        return provider

    def list(self) -> list[AIProvider]:
        return list(self._providers.values())

    def health(self) -> list[ProviderHealth]:
        return [provider.health() for provider in self.list()]
