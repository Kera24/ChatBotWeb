from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/info")
def get_system_info() -> dict[str, str]:
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "phase": settings.PHASE,
        "service": settings.SERVICE_NAME,
    }
