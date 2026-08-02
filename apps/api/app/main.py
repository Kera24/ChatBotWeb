from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.routing import APIRoute

from app.ai.dependencies import create_ai_core
from app.api.health import router as health_router
from app.api.v1.router import API_V1_ROUTER_REGISTRATIONS
from app.core.config import settings
from app.operations.correlation import safe_request_id
from app.operations.telemetry import configure_azure_monitor, normalise_route

_REQUIRED_PUBLIC_ROUTES = {
    "/api/v1/widget/{public_key}/config",
    "/api/v1/widget/{public_key}/messages",
    "/api/v1/widget/{public_key}/sessions",
}


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
        if _is_auth_preflight(request):
            response = Response(status_code=204)
        else:
            response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        if request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth"):
            _apply_auth_cors(response)
        return response

    _materialise_router(app, health_router)
    for child_router, prefix, tags in API_V1_ROUTER_REGISTRATIONS:
        _materialise_router(app, child_router, prefix=f"{settings.API_V1_PREFIX}{prefix}", tags=tags)

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.SERVICE_NAME,
        }

    _assert_required_routes(app)
    return app


def _is_auth_preflight(request: Request) -> bool:
    return request.method == "OPTIONS" and request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth")


def _apply_auth_cors(response: Response) -> None:
    response.headers.setdefault("Access-Control-Allow-Origin", settings.WEB_ORIGIN)
    response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, X-Request-ID")
    response.headers.setdefault("Vary", "Origin")


def _materialise_router(app: FastAPI, router: APIRouter, *, prefix: str = "", tags: list[str] | None = None) -> None:
    normalized_prefix = _normalise_prefix(prefix)
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        route_tags = [*(tags or []), *[tag for tag in route.tags if tag not in (tags or [])]]
        app.add_api_route(
            f"{normalized_prefix}{route.path}",
            route.endpoint,
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route_tags,
            dependencies=route.dependencies,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=route.responses,
            deprecated=route.deprecated,
            methods=list(route.methods or []),
            operation_id=route.operation_id,
            response_model_include=route.response_model_include,
            response_model_exclude=route.response_model_exclude,
            response_model_by_alias=route.response_model_by_alias,
            response_model_exclude_unset=route.response_model_exclude_unset,
            response_model_exclude_defaults=route.response_model_exclude_defaults,
            response_model_exclude_none=route.response_model_exclude_none,
            include_in_schema=route.include_in_schema,
            response_class=route.response_class,
            name=route.name,
            openapi_extra=route.openapi_extra,
            generate_unique_id_function=route.generate_unique_id_function,
        )


def _normalise_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return f"/{prefix.strip('/')}"


def _assert_required_routes(app: FastAPI) -> None:
    paths = {route.path for route in app.routes if isinstance(getattr(route, "path", None), str)}
    missing = sorted(_REQUIRED_PUBLIC_ROUTES - paths)
    if missing:
        raise RuntimeError(f"Public widget route registration failed: {', '.join(missing)}")


app = create_app()
