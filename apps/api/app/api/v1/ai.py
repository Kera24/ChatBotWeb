from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.dependencies import AICoreContainer, get_ai_core, get_default_ai_timeout
from app.ai.errors import (
    AIProviderError,
    AIProviderTimeoutError,
    ModelDisabledError,
    ModelNotFoundError,
    PromptNotFoundError,
    PromptValidationError,
    ProviderNotFoundError,
)
from app.ai.service import AICoreGenerateInput
from app.api.deps import SuperAdminDependency
from app.schemas.ai import AIGenerateRequest, AIGenerateResponse
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
    except AIProviderTimeoutError as exc:
        raise _safe_error(status.HTTP_504_GATEWAY_TIMEOUT, exc.code, exc.message) from exc
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


def _safe_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
