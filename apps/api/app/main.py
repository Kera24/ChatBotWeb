from fastapi import FastAPI, Request

from app.ai.dependencies import create_ai_core
from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.operations.correlation import safe_request_id
from app.operations.telemetry import configure_azure_monitor, normalise_route


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
    )

    app.state.ai_core = create_ai_core()
    configure_azure_monitor(app)

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = safe_request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        request.state.telemetry_route = normalise_route(request)
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        return response

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.SERVICE_NAME,
        }

    return app


app = create_app()
