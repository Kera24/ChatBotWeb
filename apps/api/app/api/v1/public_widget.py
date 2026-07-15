from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.access.channels.widget import WidgetChannelAdapter
from app.access.contracts import NormalisedAccessContext, PublicAccessRequest, new_request_id
from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import DatabaseCredentialRegistry
from app.access.credentials.service import public_credential_to_record
from app.access.errors import PublicAccessError, PublicAccessErrorDetail, error_detail
from app.access.messages.abuse.service import PublicMessageAbuseService
from app.access.messages.cost_control.service import PublicMessageCostControlService
from app.access.messages.idempotency import PublicMessageIdempotencyService
from app.access.messages.rag_adapter import PublicWidgetRAGAdapter
from app.access.messages.preparation import PublicMessagePreparationService
from app.access.messages.security import PublicMessageSecurityService
from app.access.gateway import ChannelRegistry, PublicAccessGateway
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.origin_validation.repository import list_active_origins_for_credential
from app.access.origin_validation.service import OriginValidationService
from app.access.policies.registry import default_policy_registry
from app.access.rate_limit.client_ip import extract_client_ip, parse_trusted_proxy_networks
from app.access.rate_limit.local_fallback import LocalFallbackLimiter
from app.access.rate_limit.redis_store import create_redis_rate_limit_store
from app.access.rate_limit.service import RateLimitService
from app.access.sessions.service import PublicSessionChecks, PublicSessionService
from app.ai.rag_orchestrator import RAGOrchestrator, RAGOrchestratorDependencies
from app.access.tenant_resolution.service import PublicTenantResolutionService, TenantResolutionChecks
from app.access.widget_config.public_projection import project_public_widget_configuration, public_widget_config_etag
from app.access.widget_config.repository import get_configuration_for_credential
from app.api.deps import DbSession
from app.core.config import settings
from app.db.models import Organisation, PublicCredential, Workspace
from app.services.embeddings import build_embedding_provider
from app.schemas.public_widget import PublicWidgetConfigurationResponse, PublicWidgetMessageCreateRequest, PublicWidgetMessageResponse, PublicWidgetSessionCreateRequest, PublicWidgetSessionCreateResponse

router = APIRouter(tags=["public-widget"])

MAX_PUBLIC_WIDGET_SESSION_BODY_BYTES = 16 * 1024
MAX_PUBLIC_WIDGET_MESSAGE_BODY_BYTES = 32 * 1024
_ALLOWED_SESSION_CORS_HEADERS = "Content-Type, X-Request-ID"
_ALLOWED_CONFIG_CORS_HEADERS = "If-None-Match, X-Request-ID"
_ALLOWED_MESSAGE_CORS_HEADERS = "Content-Type, Idempotency-Key, X-Request-ID"
_CONFIG_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=30"
_ERROR_CACHE_CONTROL = "no-store"
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


def _emit(event_sink: InMemoryAccessEventSink, event_type: str, *, request_id: str, trace_id: str = "unresolved", channel: str = "widget", credential_id: str | None = None, outcome: str | None = None, error_code: str | None = None, latency_ms: int | None = None) -> None:
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


def _cors_headers(origin: str, *, methods: str = "POST, OPTIONS", allowed_headers: str = _ALLOWED_SESSION_CORS_HEADERS) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": methods,
        "Access-Control-Allow-Headers": allowed_headers,
        "Access-Control-Allow-Credentials": "false",
        "Vary": "Origin",
    }


def _config_cors_headers(origin: str) -> dict[str, str]:
    return _cors_headers(origin, methods="GET, OPTIONS", allowed_headers=_ALLOWED_CONFIG_CORS_HEADERS)


def _message_cors_headers(origin: str) -> dict[str, str]:
    return _cors_headers(origin, methods="POST, OPTIONS", allowed_headers=_ALLOWED_MESSAGE_CORS_HEADERS)


async def _parse_message_body(request: Request) -> tuple[dict[str, Any] | None, PublicAccessErrorDetail | None]:
    body_bytes = await request.body()
    if len(body_bytes) > MAX_PUBLIC_WIDGET_MESSAGE_BODY_BYTES:
        return None, error_detail("message_too_large")
    if not body_bytes:
        return None, error_detail("invalid_request")
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return None, error_detail("invalid_request")
    try:
        raw_body = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, error_detail("invalid_request")
    if not isinstance(raw_body, dict):
        return None, error_detail("invalid_request")
    try:
        parsed = PublicWidgetMessageCreateRequest.model_validate(raw_body)
    except ValidationError:
        return None, error_detail("invalid_request")
    return parsed.model_dump(exclude_none=True), None


def _map_public_error(detail: PublicAccessErrorDetail) -> PublicAccessErrorDetail:
    if detail.code in _FORBIDDEN_RESPONSE_CODES_AS_INVALID_WIDGET:
        return error_detail("invalid_widget")
    if detail.code == "insecure_origin":
        return error_detail("origin_not_allowed")
    if detail.code == "unsupported_origin_scheme":
        return error_detail("malformed_origin")
    if detail.code == "unsafe_request":
        return error_detail("invalid_request")
    return detail


def _error_response(detail: PublicAccessErrorDetail, *, request_id: str, cors_origin: str | None = None, cache_errors: bool = False) -> JSONResponse:
    mapped = _map_public_error(detail)
    headers: dict[str, str] = {"Cache-Control": _ERROR_CACHE_CONTROL} if not cache_errors else {}
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
        local_fallback=LocalFallbackLimiter(enabled=settings.RATE_LIMIT_LOCAL_FALLBACK_ENABLED),
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

    def project_config_read(_request: PublicAccessRequest, context: NormalisedAccessContext, credential: object, _origin_result: object | None) -> dict[str, Any]:
        record = credential
        if not isinstance(record, CredentialRecord) or record.credential_type != "widget_public_key":
            raise PublicAccessError(error_detail("invalid_widget"))
        configuration = get_configuration_for_credential(
            db,
            organisation_id=context.organisation_id,
            workspace_id=context.workspace_id,
            credential_id=record.credential_id,
        )
        if configuration is None or configuration.status != "published" or configuration.published_at is None or int(configuration.configuration_version) <= 0:
            raise PublicAccessError(error_detail("widget_not_published"))
        payload, asset_omitted = project_public_widget_configuration(
            configuration,
            request_id=_request.request_id,
            asset_base_url=settings.PUBLIC_WIDGET_ASSET_BASE_URL or None,
        )
        etag = public_widget_config_etag(payload)
        return {
            "payload": payload,
            "etag": etag,
            "configuration_version": int(configuration.configuration_version),
            "asset_omitted": asset_omitted,
        }

    public_session_service = PublicSessionService(db=db, checks=_session_checks(db), event_sink=event_sink)
    idempotency_service = PublicMessageIdempotencyService(db=db)
    ai_core = getattr(request.app.state, "ai_core", None)
    rag_adapter = None
    security_service = None
    preparation_service = None
    if ai_core is not None:
        embedding_provider = build_embedding_provider(
            provider_name=settings.EMBEDDING_PROVIDER,
            model_name=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        rag_adapter = PublicWidgetRAGAdapter(
            orchestrator=RAGOrchestrator(
                RAGOrchestratorDependencies(db=db, ai_core=ai_core, embedding_provider=embedding_provider)
            ),
            idempotency_service=idempotency_service,
            event_sink=event_sink,
        )
        security_service = PublicMessageSecurityService(
            db=db,
            abuse_service=PublicMessageAbuseService(),
            cost_control_service=PublicMessageCostControlService(model_registry=ai_core.model_registry),
            idempotency_service=idempotency_service,
            public_session_service=public_session_service,
            event_sink=event_sink,
        )
        preparation_service = PublicMessagePreparationService(
            db=db,
            public_session_service=public_session_service,
            idempotency_service=idempotency_service,
            event_sink=event_sink,
        )
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
        public_session_service=public_session_service,
        session_creation_enricher=enrich_session_creation,
        config_read_projector=project_config_read,
        message_preparation_service=preparation_service,
        message_security_service=security_service,
        message_rag_adapter=rag_adapter,
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


def _raw_config_gateway_request(public_key: str, request: Request, request_id: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "channel": "widget",
        "method": request.method,
        "public_key": public_key,
        "origin": request.headers.get("origin"),
        "headers": _headers(request),
        "body": {},
        "query_params": dict(request.query_params),
        "channel_metadata": {},
        "client_ip": _client_ip(request),
        "user_agent": _bounded_user_agent(request),
        "rate_limit_category": "widget_config_read",
        "access_operation": "config_read",
        "allow_empty_message": True,
    }



def _raw_message_gateway_request(public_key: str, request: Request, body: dict[str, Any], request_id: str) -> dict[str, Any]:
    metadata = body.get("metadata") or {}
    if body.get("client_request_id"):
        metadata = {**metadata, "client_request_id": body["client_request_id"]}
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
        "rate_limit_category": "widget_message_send",
        "access_operation": "message_send",
    }


def _message_error_response(detail: PublicAccessErrorDetail, *, request_id: str, cors_origin: str | None = None) -> JSONResponse:
    mapped = detail
    if mapped.code in _FORBIDDEN_RESPONSE_CODES_AS_INVALID_WIDGET:
        mapped = error_detail("invalid_widget")
    elif mapped.code == "insecure_origin":
        mapped = error_detail("origin_not_allowed")
    elif mapped.code == "unsupported_origin_scheme":
        mapped = error_detail("malformed_origin")
    headers: dict[str, str] = {"Cache-Control": _ERROR_CACHE_CONTROL}
    if mapped.retry_after_seconds is not None:
        headers["Retry-After"] = str(mapped.retry_after_seconds)
    if cors_origin and mapped.code not in {"origin_not_allowed", "origin_required", "malformed_origin"}:
        headers.update(_message_cors_headers(cors_origin))
    return JSONResponse(status_code=mapped.http_status, content={"error": mapped.to_public_dict() | {"request_id": request_id}}, headers=headers)
def _handle_gateway_error(result, event_sink: InMemoryAccessEventSink, *, request_id: str, started: float, event_prefix: str) -> JSONResponse | None:
    if result.response.safe_error is None:
        return None
    detail = _map_public_error(result.response.safe_error)
    event_type = f"{event_prefix}.rejected"
    if detail.code == "rate_limited":
        event_type = f"{event_prefix}.rate_limited"
    elif detail.code in _ORIGIN_ERROR_CODES:
        event_type = f"{event_prefix}.origin_denied"
    elif detail.code == "temporarily_unavailable":
        event_type = f"{event_prefix}.unavailable"
    _emit(event_sink, event_type, request_id=request_id, trace_id=result.response.trace_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
    return _error_response(detail, request_id=request_id)


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    values = [item.strip() for item in if_none_match.split(",")]
    return "*" in values or etag in values


@router.options("/widget/{public_key}/config")
def public_widget_config_preflight(public_key: str, request: Request, db: DbSession) -> Response:
    request_id = _request_id(request)
    event_sink = _event_sink(request)
    origin = request.headers.get("origin")
    started = time.perf_counter()
    _emit(event_sink, "widget.config.requested", request_id=request_id, outcome="preflight")
    raw = _raw_config_gateway_request(public_key, request, request_id)
    try:
        result = _gateway(request, db, event_sink).validate_access(raw)
    except Exception:
        _emit(event_sink, "widget.config.unavailable", request_id=request_id, outcome="rejected", error_code="safe_internal_error", latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(error_detail("safe_internal_error"), request_id=request_id)
    error = _handle_gateway_error(result, event_sink, request_id=request_id, started=started, event_prefix="widget.config")
    if error is not None:
        return error
    if not origin:
        return _error_response(error_detail("origin_required"), request_id=request_id)
    headers = _config_cors_headers(origin)
    headers["Cache-Control"] = _CONFIG_CACHE_CONTROL
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)


@router.get("/widget/{public_key}/config", response_model=PublicWidgetConfigurationResponse)
def get_public_widget_config(public_key: str, request: Request, db: DbSession) -> JSONResponse | Response:
    request_id = _request_id(request)
    event_sink = _event_sink(request)
    started = time.perf_counter()
    _emit(event_sink, "widget.config.requested", request_id=request_id, outcome="requested")
    if request.headers.get("content-length") not in {None, "0"}:
        detail = error_detail("invalid_request")
        _emit(event_sink, "widget.config.rejected", request_id=request_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(detail, request_id=request_id)
    raw = _raw_config_gateway_request(public_key, request, request_id)
    origin = request.headers.get("origin")
    try:
        result = _gateway(request, db, event_sink).validate_access(raw)
        error = _handle_gateway_error(result, event_sink, request_id=request_id, started=started, event_prefix="widget.config")
        if error is not None:
            db.rollback()
            return error
        payload = WidgetChannelAdapter().format_config_response(result.response)
        etag = str(result.response.metadata.get("etag") or public_widget_config_etag(payload))
        headers = _config_cors_headers(origin or "")
        headers["ETag"] = etag
        headers["Cache-Control"] = _CONFIG_CACHE_CONTROL
        if any(event.event_type == "rate_limit.degraded_local_fallback" and event.request_id == request_id for event in event_sink.events):
            _emit(event_sink, "widget.config.degraded_rate_limit", request_id=request_id, trace_id=result.response.trace_id, outcome="degraded", latency_ms=int((time.perf_counter() - started) * 1000))
        if _etag_matches(request.headers.get("if-none-match"), etag):
            _emit(event_sink, "widget.config.not_modified", request_id=request_id, trace_id=result.response.trace_id, outcome="not_modified", latency_ms=int((time.perf_counter() - started) * 1000))
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
        if bool(result.response.metadata.get("asset_omitted")):
            _emit(event_sink, "widget.config.asset_omitted", request_id=request_id, trace_id=result.response.trace_id, outcome="omitted", latency_ms=int((time.perf_counter() - started) * 1000))
        _emit(event_sink, "widget.config.served", request_id=request_id, trace_id=result.response.trace_id, outcome="served", latency_ms=int((time.perf_counter() - started) * 1000))
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload, headers=headers)
    except PublicAccessError as exc:
        db.rollback()
        detail = _map_public_error(exc.detail)
        _emit(event_sink, "widget.config.rejected", request_id=request_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(detail, request_id=request_id)
    except Exception:
        db.rollback()
        _emit(event_sink, "widget.config.unavailable", request_id=request_id, outcome="rejected", error_code="safe_internal_error", latency_ms=int((time.perf_counter() - started) * 1000))
        return _error_response(error_detail("safe_internal_error"), request_id=request_id)


@router.options("/widget/{public_key}/messages")
def public_widget_message_preflight(public_key: str, request: Request, db: DbSession) -> Response:
    request_id = _request_id(request)
    event_sink = _event_sink(request)
    origin = request.headers.get("origin")
    started = time.perf_counter()
    _emit(event_sink, "widget.message.requested", request_id=request_id, outcome="preflight")
    raw = _raw_gateway_request(public_key, request, {}, request_id)
    raw["method"] = "OPTIONS"
    raw["allow_empty_message"] = True
    raw["skip_rate_limit"] = True
    raw.pop("session_operation", None)
    try:
        result = _gateway(request, db, event_sink).validate_access(raw)
    except Exception:
        _emit(event_sink, "widget.message.rejected", request_id=request_id, outcome="rejected", error_code="safe_internal_error", latency_ms=int((time.perf_counter() - started) * 1000))
        return _message_error_response(error_detail("safe_internal_error"), request_id=request_id)
    if result.response.safe_error is not None:
        detail = _map_public_error(result.response.safe_error)
        event_type = "widget.message.rejected"
        if detail.code in _ORIGIN_ERROR_CODES:
            event_type = "widget.message.origin_denied"
        _emit(event_sink, event_type, request_id=request_id, trace_id=result.response.trace_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _message_error_response(detail, request_id=request_id)
    if not origin:
        return _message_error_response(error_detail("origin_required"), request_id=request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_message_cors_headers(origin))


@router.post("/widget/{public_key}/messages", response_model=PublicWidgetMessageResponse)
async def send_public_widget_message(public_key: str, request: Request, db: DbSession) -> JSONResponse:
    request_id = _request_id(request)
    event_sink = _event_sink(request)
    started = time.perf_counter()
    cors_origin = request.headers.get("origin")
    _emit(event_sink, "widget.message.requested", request_id=request_id, outcome="requested")
    if not request.headers.get("idempotency-key"):
        detail = error_detail("idempotency_key_required")
        _emit(event_sink, "widget.message.rejected", request_id=request_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _message_error_response(detail, request_id=request_id, cors_origin=cors_origin)
    body, parse_error = await _parse_message_body(request)
    if parse_error is not None or body is None:
        detail = parse_error or error_detail("invalid_request")
        _emit(event_sink, "widget.message.rejected", request_id=request_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _message_error_response(detail, request_id=request_id, cors_origin=cors_origin)
    raw = _raw_message_gateway_request(public_key, request, body, request_id)
    try:
        result = _gateway(request, db, event_sink).validate_access(raw)
        if result.response.safe_error is not None:
            db.commit()
            detail = result.response.safe_error
            event_type = "widget.message.rejected"
            if detail.code == "rate_limited":
                event_type = "widget.message.rate_limited"
            elif detail.code in _ORIGIN_ERROR_CODES:
                event_type = "widget.message.origin_denied"
            _emit(event_sink, event_type, request_id=request_id, trace_id=result.response.trace_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
            return _message_error_response(detail, request_id=request_id, cors_origin=cors_origin)
        payload = result.response.payload
        if payload.get("stored_response") is not None:
            db.commit()
            _emit(event_sink, "widget.message.duplicate", request_id=request_id, trace_id=result.response.trace_id, outcome="duplicate", latency_ms=int((time.perf_counter() - started) * 1000))
            return JSONResponse(status_code=status.HTTP_200_OK, content=payload["stored_response"], headers=_message_cors_headers(cors_origin or ""))
        if payload.get("safe_error_code"):
            db.rollback()
            detail = error_detail(str(payload["safe_error_code"]))
            _emit(event_sink, "widget.message.rejected", request_id=request_id, trace_id=result.response.trace_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
            return _message_error_response(detail, request_id=request_id, cors_origin=cors_origin)
        if result.response.status != "message_completed" or payload.get("public_response") is None:
            db.rollback()
            detail = error_detail("temporarily_unavailable")
            _emit(event_sink, "widget.message.rejected", request_id=request_id, trace_id=result.response.trace_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
            return _message_error_response(detail, request_id=request_id, cors_origin=cors_origin)
        db.commit()
        public_response = dict(payload["public_response"])
        _emit(event_sink, "widget.message.accepted", request_id=request_id, trace_id=result.response.trace_id, outcome="accepted", latency_ms=int((time.perf_counter() - started) * 1000))
        _emit(event_sink, "widget.message.response_projected", request_id=request_id, trace_id=result.response.trace_id, outcome="projected", latency_ms=int((time.perf_counter() - started) * 1000))
        if public_response.get("fallback_used"):
            _emit(event_sink, "widget.message.fallback", request_id=request_id, trace_id=result.response.trace_id, outcome="fallback", latency_ms=int((time.perf_counter() - started) * 1000))
        return JSONResponse(status_code=status.HTTP_200_OK, content=public_response, headers=_message_cors_headers(cors_origin or ""))
    except PublicAccessError as exc:
        db.commit()
        detail = exc.detail
        _emit(event_sink, "widget.message.rejected", request_id=request_id, outcome="rejected", error_code=detail.code, latency_ms=int((time.perf_counter() - started) * 1000))
        return _message_error_response(detail, request_id=request_id, cors_origin=cors_origin)
    except Exception:
        db.rollback()
        _emit(event_sink, "widget.message.rejected", request_id=request_id, outcome="rejected", error_code="safe_internal_error", latency_ms=int((time.perf_counter() - started) * 1000))
        return _message_error_response(error_detail("safe_internal_error"), request_id=request_id, cors_origin=cors_origin)

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
