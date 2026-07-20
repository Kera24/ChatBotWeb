from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings
from app.services.embeddings import build_embedding_provider

router = APIRouter(tags=["system"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(response: Response, db: DbSession) -> dict:
    checks: dict[str, str] = {}
    ready_status = "ready"
    try:
        db.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failed"
        ready_status = "not_ready"
    try:
        build_embedding_provider(
            provider_name=settings.EMBEDDING_PROVIDER,
            model_name=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        checks["retrieval"] = "ok"
    except Exception:
        checks["retrieval"] = "failed"
        ready_status = "not_ready"
    checks["public_widget"] = "ok"
    if ready_status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": ready_status, "checks": checks}

