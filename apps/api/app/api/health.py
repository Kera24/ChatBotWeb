from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings
from app.services.embeddings import build_embedding_provider

router = APIRouter(tags=["system"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


def check_redis() -> str:
    """Ping Redis for visibility only; overridden in tests via dependency_overrides."""
    try:
        import redis as redis_module

        client = redis_module.Redis.from_url(
            settings.REDIS_URL, socket_timeout=1.5, socket_connect_timeout=1.5
        )
        return "ok" if client.ping() else "failed"
    except Exception:
        return "failed"


@router.get("/health/ready")
def ready(response: Response, db: DbSession, redis_status: str = Depends(check_redis)) -> dict:
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
    # Redis backs public-widget rate limiting and idempotency. It is reported
    # as a visible check but does not flip overall readiness to not_ready:
    # core chat/RAG functionality keeps working without Redis, only rate
    # limiting degrades (see docs/06_Operations/Monitoring_Runbook.md) - an
    # orchestrator should not kill/restart the app over this alone, but a
    # human/alert should still see it.
    checks["redis"] = redis_status
    checks["public_widget"] = "ok"
    if ready_status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": ready_status, "checks": checks}

