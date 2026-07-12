from datetime import UTC, datetime
from enum import StrEnum
from time import perf_counter
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.errors import AIProviderHealthCheckError
if TYPE_CHECKING:
    from app.ai.provider_registry import ProviderRegistry
    from app.ai.providers.base import AIProvider


class ProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ProviderHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_key: str
    status: ProviderHealthStatus
    checked_at: datetime
    latency_ms: int | None = None
    message: str | None = None
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHealthService:
    def __init__(self, provider_registry: "ProviderRegistry") -> None:
        self.provider_registry = provider_registry
        self._health_by_provider: dict[str, ProviderHealth] = {}

    def get(self, provider_key: str) -> ProviderHealth:
        self.provider_registry.get(provider_key)
        existing = self._health_by_provider.get(provider_key)
        if existing is not None:
            return existing
        return ProviderHealth(
            provider_key=provider_key,
            status=ProviderHealthStatus.UNKNOWN,
            checked_at=datetime.now(UTC),
            message="Provider health has not been checked yet.",
        )

    def check_provider(self, provider: "AIProvider") -> ProviderHealth:
        self.provider_registry.get(provider.provider_key)
        started_at = perf_counter()
        try:
            checked = provider.health()
        except Exception as exc:  # pragma: no cover - defensive guard for future providers
            failure = self.update_after_failure(provider.provider_key, message=str(exc))
            raise AIProviderHealthCheckError("Provider health check failed.") from exc
        latency_ms = int((perf_counter() - started_at) * 1000)
        previous = self._health_by_provider.get(provider.provider_key)
        health = checked.model_copy(
            update={
                "latency_ms": latency_ms,
                "consecutive_failures": previous.consecutive_failures if previous else checked.consecutive_failures,
                "last_success_at": previous.last_success_at if previous else checked.last_success_at,
                "last_failure_at": previous.last_failure_at if previous else checked.last_failure_at,
            }
        )
        self._health_by_provider[provider.provider_key] = health
        return health

    def update_after_success(self, provider_key: str) -> ProviderHealth:
        self.provider_registry.get(provider_key)
        now = datetime.now(UTC)
        current = self.get(provider_key)
        health = ProviderHealth(
            provider_key=provider_key,
            status=ProviderHealthStatus.HEALTHY,
            checked_at=now,
            message="Provider execution succeeded.",
            consecutive_failures=0,
            last_success_at=now,
            last_failure_at=current.last_failure_at,
            metadata=current.metadata,
        )
        self._health_by_provider[provider_key] = health
        return health

    def update_after_failure(self, provider_key: str, *, message: str | None = None) -> ProviderHealth:
        self.provider_registry.get(provider_key)
        now = datetime.now(UTC)
        current = self.get(provider_key)
        health = ProviderHealth(
            provider_key=provider_key,
            status=ProviderHealthStatus.UNAVAILABLE,
            checked_at=now,
            message=message or "Provider execution failed.",
            consecutive_failures=current.consecutive_failures + 1,
            last_success_at=current.last_success_at,
            last_failure_at=now,
            metadata=current.metadata,
        )
        self._health_by_provider[provider_key] = health
        return health

    def set_status(
        self,
        provider_key: str,
        status: ProviderHealthStatus,
        *,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderHealth:
        self.provider_registry.get(provider_key)
        now = datetime.now(UTC)
        current = self._health_by_provider.get(provider_key)
        health = ProviderHealth(
            provider_key=provider_key,
            status=status,
            checked_at=now,
            message=message,
            consecutive_failures=current.consecutive_failures if current else 0,
            last_success_at=current.last_success_at if current else None,
            last_failure_at=current.last_failure_at if current else None,
            metadata=metadata or {},
        )
        self._health_by_provider[provider_key] = health
        return health

    def list(self) -> list[ProviderHealth]:
        return [self.get(provider.provider_key) for provider in self.provider_registry.list()]
