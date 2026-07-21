from pydantic import BaseModel, Field, field_validator

from app.ai.errors import InvalidExecutionPolicyError


class ProviderExecutionPolicy(BaseModel):
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_attempts: int = Field(default=2, ge=1, le=5)
    retryable_error_types: tuple[str, ...] = (
        "AI_PROVIDER_TIMEOUT",
        "AI_PROVIDER_TIMEOUT_EXHAUSTED",
        "AI_PROVIDER_UNAVAILABLE",
    )
    retry_backoff_seconds: float = Field(default=0.0, ge=0, le=5)
    health_check_required: bool = False
    fail_fast_when_unhealthy: bool = True

    @field_validator("retryable_error_types")
    @classmethod
    def validate_retryable_error_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise InvalidExecutionPolicyError("At least one retryable error type must be configured.")
        return value
