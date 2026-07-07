from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
    )

    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.SERVICE_NAME,
        }

    return app


app = create_app()
