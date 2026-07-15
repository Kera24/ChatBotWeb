from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.access.channels.widget import WidgetChannelAdapter
from app.access.contracts import NormalisedAccessContext, PublicAccessRequest, new_request_id
from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import DatabaseCredentialRegistry
from app.access.credentials.service import public_credential_to_record
from app.access.errors import PublicAccessError, PublicAccessErrorDetail, error_detail
from app.access.gateway import ChannelRegistry, PublicAccessGateway
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.origin_validation.repository import list_active_origins_for_credential
from app.access.origin_validation.service import OriginValidationService
from app.access.policies.registry import default_policy_registry
from app.access.rate_limit.client_ip import extract_client_ip, parse_trusted_proxy_networks
from app.access.rate_limit.redis_store import create_redis_rate_limit_store
from app.access.rate_limit.service import RateLimitService
from app.access.sessions.service import PublicSessionChecks, PublicSessionService
from app.access.tenant_resolution.service import PublicTenantResolutionService, TenantResolutionChecks
from app.access.widget_config.repository import get_configuration_for_credential
from app.api.deps import DbSession
from app.core.config import settings
from app.db.models import Organisation, PublicCredential, Workspace
from app.schemas.public_widget import PublicWidgetSessionCreateRequest, PublicWidgetSessionCreateResponse

router = APIRouter(tags=["public-widget"])

MAX_PUBLIC_WIDGET_SESSION_BODY_BYTES = 16 * 1024
_ALLOWED_CORS_HEADERS = "Content-Type, X-Request-ID"
_FORBIDDEN_RESPONSE_CODES_AS_INVALID_WIDGET = {"invalid_credential", "disabled_credential", "expired_credential", "widget_not_published"}
_ORIGIN_ERROR_CODES = {"origin_required", "origin_not_allowed", "malformed_origin", "insecure_origin", "unsupported_origin_scheme"}


def _request_id(request: Request) -> str:
    header = request.headers.get("x-request-id")
    if header and 0 < len(header) <= 120:
        return header
    return new_request_id()


def _headers(request: Request) -> dict[str, str]:
    return {key: value for key, value in request.headers.items()}


def _bounded_user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    if value is None:
        return None
    return value[:256]


def _client_ip(request: Request) -> str:
    peer_ip = request.client.host if request.client else "127.0.0.1"
    try:
        networks = parse_trusted_proxy_networks(settings.TRUSTED_PROXY_NETWORKS)
        return extract_client_ip(peer_ip=peer_ip, headers=_headers(request), trusted_proxy_networks=networks).identity
    except Exception:
        return "127.0.0.1"


async def _parse_body(request: Request) -> tuple[dict[str, Any] | None, PublicAccessErrorDetail | None]:
    body_bytes = await request.body()
    if len(body_bytes) > MAX_PUBLIC_WIDGET_SESSION_BODY_BYTES:
        return None, error_detail("request_too_large")
    if not body_bytes:
        return {}, None
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return None, error_detail("invalid_request")
    try:
        raw_body = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, error_detail("invalid_request")
    if raw_body is None:
        raw_body = {}
    if not isinstance(raw_body, dict):
        return None, error_detail("invalid_request")
    try:
        parsed = PublicWidgetSessionCreateRequest.model_validate(raw_body)
    except ValidationError:
        return None, error_detail("invalid_request")
    return parsed.model_dump(exclude_none=True), None


def _event_sink(request: Request) -> InMemoryAccessEventSink:
    existing = getattr(request.app.state, "public_widget_event_sink", None)
    if existing is not None:
        return existing
    return InMemoryAccessEventSink()


def _emit(event_sink: InMemoryAccessEventSink, event_type: str, *, request_id: str, trace_id: str = "unresolved", channel: str = "widget", credential_id: str | None = None, outcome: str | None = None, error_code: str | None = None, latency_ms: int | None = None, environment: str | None = None) -> None:
    event_sink.emit(
        AccessEvent(
            event_type=event_type,
            request_id=request_id,
            trace_id=trace_id,
            channel=channel,
            credential_id=credential_id,
            outcome=outcome,
            error_code=error_code,
            latency_ms=latency_ms,
        )
    )


def _cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": _ALLOWED_CORS_HEADERS,
        "Access-Control-Allow-Credentials": "false",
        "Vary": "Origin",
    }


def _map_public_error(detail: PublicAccessErrorDetail) -> PublicAccessErrorDetail:
    if detail.code in _FORBIDDEN_RESPONSE_CODES_AS_INVALID_WIDGET:
        return error_detail("invalid_widget")
    if detail.code == "insecure_origin":
        return error_detail("origin_not_allowed")
    if detail.code == "unsupported_origin_scheme":
        return error_detail("malformed_origin")
    return detail


def _error_response(detail: PublicAccessErrorDetail, *, request_id: str, cors_origin: str | None = None) -> JSONResponse:
    mapped = _map_public_error(detail)
    headers: dict[str, str] = {}
    if mapped.retry_after_seconds is not None:
        headers["Retry-After"] = str(mapped.retry_after_seconds)
    if cors_origin and mapped.code not in {"origin_not_allowed", "origin_required", "malformed_origin"}:
        headers.update(_cors_headers(cors_origin))
    body = {"error": mapped.to_public_dict() | {"request_id": request_id}}
    return JSONResponse(status_code=mapped.http_status, content=body, headers=headers)


def _tenant_checks(db: Session) -> TenantResolutionChecks:
    return TenantResolutionChecks(
        organisation_is_active=lambda organisation_id: (db.get(Organisation, organisation_id) is not None and db.get(Organisation, organisation_id).status == "active"),
        workspace_is_active=lambda workspace_id: (db.get(Workspace, workspace_id) is not None and db.get(Workspace, workspace_id).status == "active"),
        workspace_belongs_to_organisation=lambda workspace_id, organisation_id: (db.get(Workspace, workspace_id) is not None and db.get(Workspace, workspace_id).organisation_id == organisation_id),
    )


def _session_checks(db: Session) -> PublicSessionChecks:
    def lookup(credential_id: str) -> CredentialRecord | None:
        credential = db.get(PublicCredential, credential_id)
        return public_credential_to_record(credential) if credential is not None else None

    return PublicSessionChecks(
        organisation_is_active=lambda organisation_id: (db.get(Organisation, organisation_id) is not None and db.get(Organisation, organisation_id).status == "active"),
        workspace_is_active=lambda workspace_id: (db.get(Workspace, workspace_id) is not None and db.get(Workspace, workspace_id).status == "active"),
        credential_lookup=lookup,
        policy_requires_origin=lambda policy_profile: policy_profile == "widget",
    )


def _rate_limit_service(request: Request, event_sink: InMemoryAccessEventSink) -> RateLimitService:
    store = getattr(request.app.state, "public_widget_rate_limit_store", None)
    if store is None:
        store = create_redis_rate_limit_store(redis_url=settings.REDIS_URL, timeout_seconds=settings.RATE_LIMIT_REDIS_TIMEOUT_SECONDS)
    return RateLimitService(
        store=store,
        identity_secret=settings.RATE_LIMIT_IDENTITY_SECRET,
        redis_prefix=settings.RATE_LIMIT_REDIS_PREFIX,
        event_sink=event_sink,
    )


def _gateway(request: Request, db: Session, event_sink: InMemoryAccessEventSink) -> PublicAccessGateway:
    policy_registry = default_policy_registry()

    def enrich_session_creation(_request: PublicAccessRequest, context: NormalisedAccessContext, credential: object) -> dict[str, Any]:
        record = credential
        if not isinstance(record, CredentialRecord) or record.credential_type != "widget_public_key":
            raise PublicAccessError(error_detail("invalid_widget"))
        configuration = get_configuration_for_credential(
            db,
            organisation_id=context.organisation_id,
            workspace_id=context.workspace_id,
            credential_id=record.credential_id,
        )
        if configuration is None or configuration.status != "published" or configuration.published_at is None:
            raise PublicAccessError(error_detail("widget_not_published"))
        return {
            "session_metadata": {"configuration_version": configuration.configuration_version},
            "response_payload": {
                "configuration_version": configuration.configuration_version,
                "remaining_messages": policy_registry.resolve(context.policy_profile).max_messages_per_session,
                "capabilities": {
                    "can_send_messages": True,
                    "conversation_history_enabled": bool(configuration.allow_conversation_history),
                    "citations_enabled": bool(configuration.show_citations),
                },
            },
        }

    return PublicAccessGateway(
        channel_registry=ChannelRegistry([WidgetChannelAdapter()]),
        tenant_resolution_service=PublicTenantResolutionService(
            credential_registry=DatabaseCredentialRegistry(db),
            policy_registry=policy_registry,
            checks=_tenant_checks(db),
        ),
        policy_registry=policy_registry,
        event_sink=event_sink,
        origin_validation_service=OriginValidationService(
            origin_lookup=lambda credential_id, environment: list_active_origins_for_credential(db, credential_id=credential_id, environment=environment),
            event_sink=event_sink,
        ),
        rate_limit_service=_rate_limit_service(request, event_sink),
        public_session_service=PublicSessionService(db=db, checks=_session_checks(db), event_sink=event_sink),
        session_creation_enricher=enrich_session_creation,
    )


def _raw_gateway_request(public_key: str, request: Request, body: dict[str, Any], request_id: str) -> dict[str, Any]:
    metadata = body.get("metadata") or {}
    if body.get("client_request_id"):
        metadata = {**metadata, "client_request_id": body["client_request_id"]}
    if body.get("requested_language"):
        metadata = {**metadata, "requested_language": body["requested_language"]}
    return {
        "request_id": request_id,
        "channel": "widget",
        "method": request.method,
        "public_key": public_key,
        "origin": request.headers.get("origin"),
        "headers": _headers(request),
        "body": body,
        "channel_metadata": metadata,
        "client_ip": _client_ip(request),
        "user_agent": _bounded_user_agent(request),
        "rate_limit_category": "widget_session_create",
        "session_operation": "session_creation",
    }


@router.options("/widget/{public_key}/sessions")
def public_widget_session_preflight(public_key: str, request: Request, db: DbSession) -> Response:
    request_id = _request_id(request)
    event_sink = _event_sink(request)
    origin = request.headers.get("origin")
    started = time.perf_counter()
    _emit(event_sink, "widget.session.requested", request_id=request_id, outcome="preflight")
    raw = _raw_gateway_request(public_key, request, {}, request_id)
    raw["method"] = "OPTIONS"
    raw["allow_empty_message"] = True
    raw["skip_rate_limit"] = True
    raw.pop("session_operation", None)
    try:
        result = _gateway(request, db, event_sink).validate_access(raw)
    except Exception:
        _emit(event_sink, "widget.session.unavailable", request_id=request_id, outcome="rejected", error_code="safe_internal_error", latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(error_detail("safe_internal_error"), request_id=request_id)
    if result.response.safe_error is not None:
        detail = _map_public_error(result.response.safe_error)
        event_type = "widget.session.origin_denied" if detail.code in _ORIGIN_ERROR_CODES else "widget.session.rejected"
        _emit(event_sink, event_type, request_id=request_id, trace_id=result.response.trace_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(detail, request_id=request_id)
    if not origin:
        return _error_response(error_detail("origin_required"), request_id=request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_cors_headers(origin))


@router.post("/widget/{public_key}/sessions", response_model=PublicWidgetSessionCreateResponse)
async def create_public_widget_session(public_key: str, request: Request, db: DbSession) -> JSONResponse:
    request_id = _request_id(request)
    event_sink = _event_sink(request)
    started = time.perf_counter()
    _emit(event_sink, "widget.session.requested", request_id=request_id, outcome="requested")
    body, parse_error = await _parse_body(request)
    if parse_error is not None or body is None:
        detail = parse_error or error_detail("invalid_request")
        _emit(event_sink, "widget.session.rejected", request_id=request_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(detail, request_id=request_id)
    raw = _raw_gateway_request(public_key, request, body, request_id)
    cors_origin = request.headers.get("origin")
    try:
        result = _gateway(request, db, event_sink).validate_access(raw)
        if result.response.safe_error is not None:
            db.rollback()
            detail = _map_public_error(result.response.safe_error)
            event_type = "widget.session.rejected"
            if detail.code == "rate_limited":
                event_type = "widget.session.rate_limited"
            elif detail.code in _ORIGIN_ERROR_CODES:
                event_type = "widget.session.origin_denied"
            elif detail.code == "temporarily_unavailable":
                event_type = "widget.session.unavailable"
            _emit(event_sink, event_type, request_id=request_id, trace_id=result.response.trace_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
            return _error_response(detail, request_id=request_id)
        db.commit()
        payload = WidgetChannelAdapter().format_response(result.response)
        _emit(event_sink, "widget.session.created", request_id=request_id, trace_id=result.response.trace_id, outcome="created", latency_ms=int((time.perf_counter() - started) * 1000))
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=payload, headers=_cors_headers(cors_origin or ""))
    except PublicAccessError as exc:
        db.rollback()
        detail = _map_public_error(exc.detail)
        _emit(event_sink, "widget.session.rejected", request_id=request_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(detail, request_id=request_id)
    except Exception:
        db.rollback()
        _emit(event_sink, "widget.session.unavailable", request_id=request_id, outcome="rejected", error_code="safe_internal_error", latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(error_detail("safe_internal_error"), request_id=request_id)