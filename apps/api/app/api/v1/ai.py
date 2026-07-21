from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.accounting import AIUsageRecord
from app.ai.dependencies import AICoreContainer, get_ai_core, get_default_ai_timeout
from app.ai.errors import (
    AIProviderDegradedError,
    AIProviderError,
    AIProviderHealthCheckError,
    AIProviderRetryExhaustedError,
    AIProviderTimeoutError,
    AIProviderTimeoutExhaustedError,
    AIProviderUnavailableError,
    InvalidExecutionPolicyError,
    ModelDisabledError,
    ModelNotFoundError,
    PromptNotFoundError,
    PromptValidationError,
    ProviderNotFoundError,
)
from app.ai.health import ProviderHealth
from app.ai.service import AICoreGenerateInput
from app.api.deps import SuperAdminDependency
from app.schemas.ai import (
    AIGenerateRequest,
    AIGenerateResponse,
    AIProviderHealthResponse,
    AIProviderModelResponse,
    AIProviderResponse,
    AIUsageRecordResponse,
)
from app.schemas.common import success_response

router = APIRouter()

AICoreDependency = Annotated[AICoreContainer, Depends(get_ai_core)]
TimeoutDependency = Annotated[float, Depends(get_default_ai_timeout)]


@router.post("/generate")
def generate_ai_response(
    payload: AIGenerateRequest,
    _current_user: SuperAdminDependency,
    ai_core: AICoreDependency,
    timeout_seconds: TimeoutDependency,
) -> dict[str, object]:
    """Development/internal-only AI generation endpoint.

    This is not a public chat endpoint and does not perform retrieval or RAG orchestration.
    """

    try:
        response = ai_core.service.generate(
            AICoreGenerateInput(
                prompt_key=payload.prompt_key,
                model_key=payload.model_key,
                variables=payload.variables,
                simulate_failure=payload.simulate_failure,
                simulate_timeout=payload.simulate_timeout,
                simulate_transient_failures=payload.simulate_transient_failures,
                timeout_seconds=timeout_seconds,
            )
        )
    except ProviderNotFoundError as exc:
        raise _safe_error(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
    except ModelDisabledError as exc:
        raise _safe_error(status.HTTP_400_BAD_REQUEST, exc.code, exc.message) from exc
    except ModelNotFoundError as exc:
        raise _safe_error(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
    except PromptNotFoundError as exc:
        raise _safe_error(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
    except PromptValidationError as exc:
        raise _safe_error(status.HTTP_400_BAD_REQUEST, exc.code, exc.message) from exc
    except InvalidExecutionPolicyError as exc:
        raise _safe_error(status.HTTP_400_BAD_REQUEST, exc.code, exc.message) from exc
    except AIProviderTimeoutExhaustedError as exc:
        raise _safe_error(status.HTTP_504_GATEWAY_TIMEOUT, exc.code, exc.message) from exc
    except AIProviderTimeoutError as exc:
        raise _safe_error(status.HTTP_504_GATEWAY_TIMEOUT, exc.code, exc.message) from exc
    except AIProviderRetryExhaustedError as exc:
        raise _safe_error(status.HTTP_502_BAD_GATEWAY, exc.code, exc.message) from exc
    except AIProviderUnavailableError as exc:
        raise _safe_error(status.HTTP_503_SERVICE_UNAVAILABLE, exc.code, exc.message) from exc
    except AIProviderDegradedError as exc:
        raise _safe_error(status.HTTP_503_SERVICE_UNAVAILABLE, exc.code, exc.message) from exc
    except AIProviderHealthCheckError as exc:
        raise _safe_error(status.HTTP_503_SERVICE_UNAVAILABLE, exc.code, exc.message) from exc
    except AIProviderError as exc:
        raise _safe_error(status.HTTP_502_BAD_GATEWAY, exc.code, exc.message) from exc

    data = AIGenerateResponse(
        text=response.text,
        provider_key=response.provider_key,
        model_key=response.model_key,
        provider_model_name=response.provider_model_name,
        prompt_key=response.prompt_key,
        prompt_version=response.prompt_version,
        prompt_hash=response.prompt_hash,
        token_usage=response.token_usage,
        latency_ms=response.latency_ms,
        finish_reason=response.finish_reason,
    ).model_dump(mode="json")
    return success_response(data)


@router.get("/usage")
def list_ai_usage_records(
    _current_user: SuperAdminDependency,
    ai_core: AICoreDependency,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, object]:
    """Development/internal-only recent AI usage records endpoint."""

    records = ai_core.accounting_service.list_recent(limit=limit)
    data = [_usage_record_response(record).model_dump(mode="json") for record in records]
    return success_response(data)


@router.get("/providers")
def list_ai_providers(
    _current_user: SuperAdminDependency,
    ai_core: AICoreDependency,
) -> dict[str, object]:
    """Development/internal-only provider registry and health endpoint."""

    data = []
    for provider in ai_core.provider_registry.list():
        health = ai_core.health_service.get(provider.provider_key)
        models = [model for model in ai_core.model_registry.list() if model.provider_key == provider.provider_key]
        data.append(
            AIProviderResponse(
                provider_key=provider.provider_key,
                display_name=provider.display_name,
                capabilities=provider.capabilities,
                current_health=_health_response(health),
                registered_models=[
                    AIProviderModelResponse(
                        model_key=model.model_key,
                        provider_model_name=model.provider_model_name,
                        display_name=model.display_name,
                        enabled=model.enabled,
                    )
                    for model in models
                ],
            ).model_dump(mode="json")
        )
    return success_response(data)


@router.get("/providers/{provider_key}/health")
def get_ai_provider_health(
    provider_key: str,
    _current_user: SuperAdminDependency,
    ai_core: AICoreDependency,
) -> dict[str, object]:
    try:
        health = ai_core.health_service.get(provider_key)
    except ProviderNotFoundError as exc:
        raise _safe_error(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
    return success_response(_health_response(health).model_dump(mode="json"))


@router.post("/providers/{provider_key}/health-check")
def check_ai_provider_health(
    provider_key: str,
    _current_user: SuperAdminDependency,
    ai_core: AICoreDependency,
) -> dict[str, object]:
    try:
        provider = ai_core.provider_registry.get(provider_key)
        health = ai_core.health_service.check_provider(provider)
    except ProviderNotFoundError as exc:
        raise _safe_error(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
    except AIProviderHealthCheckError as exc:
        raise _safe_error(status.HTTP_503_SERVICE_UNAVAILABLE, exc.code, exc.message) from exc
    return success_response(_health_response(health).model_dump(mode="json"))


def _usage_record_response(record: AIUsageRecord) -> AIUsageRecordResponse:
    return AIUsageRecordResponse(
        execution_id=record.execution_id,
        created_at=record.created_at.isoformat(),
        organisation_id=record.organisation_id,
        workspace_id=record.workspace_id,
        provider_key=record.provider_key,
        model_key=record.model_key,
        provider_model_name=record.provider_model_name,
        prompt_key=record.prompt_key,
        prompt_version=record.prompt_version,
        prompt_hash=record.prompt_hash,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        total_tokens=record.total_tokens,
        estimated_input_cost=record.estimated_input_cost,
        estimated_output_cost=record.estimated_output_cost,
        total_estimated_cost=record.total_estimated_cost,
        latency_ms=record.latency_ms,
        finish_reason=record.finish_reason,
        outcome=record.outcome,
        attempt_count=record.attempt_count,
        final_attempt_number=record.final_attempt_number,
        retry_performed=record.retry_performed,
        timeout_seconds=record.timeout_seconds,
        provider_health_at_start=record.provider_health_at_start,
        provider_health_at_end=record.provider_health_at_end,
        error_code=record.error_code,
        error_message=record.error_message,
    )


def _health_response(health: ProviderHealth) -> AIProviderHealthResponse:
    return AIProviderHealthResponse(
        provider_key=health.provider_key,
        status=health.status,
        checked_at=health.checked_at.isoformat(),
        latency_ms=health.latency_ms,
        message=health.message,
        consecutive_failures=health.consecutive_failures,
        last_success_at=health.last_success_at.isoformat() if health.last_success_at else None,
        last_failure_at=health.last_failure_at.isoformat() if health.last_failure_at else None,
    )


def _safe_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
