from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.observability.redaction import redact_free_text
from app.operations.correlation import safe_request_id
from app.operations.logging import log_operational_event

logger = logging.getLogger("chatbotweb.errors")

# Public widget responses follow app.api.v1.public_widget._error_response's
# {"error": {...}, "request_id": ...} envelope (consumed by the widget SDK's
# SafeErrorResponse contract); every other route follows the HTTPException
# {"detail": {...}} shape already used by app.api.v1.ai._safe_error and
# app.api.deps's RBAC dependencies. This handler is a last-resort backstop -
# public widget endpoints already catch Exception per-route - so it must
# mirror both conventions rather than introduce a third.
_WIDGET_ROUTE_PREFIX = f"{settings.API_V1_PREFIX}/widget/"
_WIDGET_ERROR_CODE = "safe_internal_error"
_WIDGET_ERROR_MESSAGE = "The request could not be completed."
_GENERIC_ERROR_CODE = "internal_server_error"
_GENERIC_ERROR_MESSAGE = "An unexpected error occurred. Please try again or contact support if the problem persists."
_MAX_LOGGED_TRACEBACK_CHARS = 4000


def install_global_exception_handler(app: FastAPI) -> None:
    app.add_exception_handler(Exception, _handle_unexpected_exception)


async def _handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or safe_request_id(request.headers.get("x-request-id"))
    trace_id = getattr(request.state, "trace_id", None) or "unresolved"
    route = getattr(request.state, "telemetry_route", None) or request.url.path

    _log_unexpected_exception(exc, request_id=request_id, trace_id=trace_id, route=route, method=request.method)

    if route.startswith(_WIDGET_ROUTE_PREFIX):
        body: dict[str, object] = {
            "error": {"code": _WIDGET_ERROR_CODE, "message": _WIDGET_ERROR_MESSAGE, "retryable": False},
            "request_id": request_id,
        }
    else:
        body = {"detail": {"code": _GENERIC_ERROR_CODE, "message": _GENERIC_ERROR_MESSAGE, "request_id": request_id}}

    return JSONResponse(
        status_code=500,
        content=body,
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


def _log_unexpected_exception(exc: Exception, *, request_id: str, trace_id: str, route: str, method: str) -> None:
    # Never allow a logging failure to prevent the safe response above from
    # being returned - this handler is itself the last line of defense.
    try:
        raw_traceback = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        safe_traceback = redact_free_text(raw_traceback).text
        # Keep the tail, not the head: the actual raise site and exception
        # message (the actionable part for debugging) are the last lines of
        # a formatted traceback, while the truncation budget is easily
        # consumed by framework/middleware frames above them.
        logger.error(safe_traceback[-_MAX_LOGGED_TRACEBACK_CHARS:])
        log_operational_event(
            logger,
            {
                "event_type": "api.unhandled_exception",
                "severity": "error",
                "request_id": request_id,
                "trace_id": trace_id,
                "route": route,
                "method": method,
                "status_code": 500,
                "exception_type": type(exc).__name__,
            },
            level=logging.ERROR,
        )
    except Exception:
        logger.error("Failed to log unhandled exception metadata for request_id=%s", request_id)
