from dataclasses import dataclass, replace
from collections.abc import Callable
from typing import Any

from app.access.channels.base import PublicChannelAdapter
from app.access.contracts import NormalisedAccessContext, PublicAccessRequest, PublicAccessResponse
from app.access.errors import PublicAccessError, error_detail, raise_public_error
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.origin_validation.contracts import OriginValidationRequest, OriginValidationResult
from app.access.origin_validation.service import OriginValidationService
from app.access.policies.registry import AccessPolicyRegistry
from app.access.rate_limit.contracts import RateLimitRequest
from app.access.rate_limit.service import RateLimitService
from app.access.sessions.contracts import CreatePublicSessionCommand, ValidatePublicSessionCommand
from app.access.sessions.service import PublicSessionService
from app.access.tenant_resolution.service import PublicTenantResolutionService


class DuplicateChannelError(ValueError):
    pass


SessionCreationEnricher = Callable[[PublicAccessRequest, NormalisedAccessContext, object], dict[str, Any]]
ConfigReadProjector = Callable[[PublicAccessRequest, NormalisedAccessContext, object, OriginValidationResult | None], dict[str, Any]]


class ChannelRegistry:
    def __init__(self, adapters: list[PublicChannelAdapter] | None = None) -> None:
        self._adapters: dict[str, PublicChannelAdapter] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: PublicChannelAdapter) -> None:
        if adapter.channel_key in self._adapters:
            raise DuplicateChannelError("Channel adapter already registered.")
        self._adapters[adapter.channel_key] = adapter

    def resolve(self, channel_key: str) -> PublicChannelAdapter:
        adapter = self._adapters.get(channel_key)
        if adapter is None:
            raise_public_error("unsupported_channel")
        return adapter


@dataclass(frozen=True)
class ValidatedAccessResult:
    request: PublicAccessRequest
    context: NormalisedAccessContext
    response: PublicAccessResponse


class PublicAccessGateway:
    def __init__(
        self,
        *,
        channel_registry: ChannelRegistry,
        tenant_resolution_service: PublicTenantResolutionService,
        policy_registry: AccessPolicyRegistry,
        event_sink: InMemoryAccessEventSink,
        origin_validation_service: OriginValidationService | None = None,
        rate_limit_service: RateLimitService | None = None,
        public_session_service: PublicSessionService | None = None,
        session_creation_enricher: SessionCreationEnricher | None = None,
        config_read_projector: ConfigReadProjector | None = None,
    ) -> None:
        self.channel_registry = channel_registry
        self.tenant_resolution_service = tenant_resolution_service
        self.policy_registry = policy_registry
        self.event_sink = event_sink
        self.origin_validation_service = origin_validation_service
        self.rate_limit_service = rate_limit_service
        self.public_session_service = public_session_service
        self.session_creation_enricher = session_creation_enricher
        self.config_read_projector = config_read_projector

    def validate(self, raw_request: dict[str, Any]) -> PublicAccessResponse:
        return self.validate_access(raw_request).response

    def validate_access(self, raw_request: dict[str, Any]) -> ValidatedAccessResult:
        request_id = str(raw_request.get("request_id") or "unparsed")
        trace_id = "unresolved"
        channel = str(raw_request.get("channel") or "")
        self._emit("access.request.received", request_id=request_id, trace_id=trace_id, channel=channel)
        request: PublicAccessRequest | None = None
        context: NormalisedAccessContext | None = None
        try:
            adapter = self.channel_registry.resolve(channel)
            self._emit("access.channel.resolved", request_id=request_id, trace_id=trace_id, channel=channel, outcome="resolved")
            parsed = adapter.parse_request(raw_request)
            adapter.validate_request_shape(parsed)
            credential = adapter.extract_public_credential(parsed)
            message = adapter.normalise_message(parsed)
            request = PublicAccessRequest(
                request_id=str(parsed.get("request_id") or request_id),
                channel=adapter.channel_key,
                public_credential=credential,
                public_session_token=adapter.extract_session_token(parsed),
                origin=adapter.extract_origin(parsed),
                client_ip=parsed.get("client_ip"),
                user_agent=parsed.get("user_agent"),
                message=message,
                channel_metadata=dict(parsed.get("channel_metadata", {})),
            )
            context, credential_record = self.tenant_resolution_service.resolve(request)
            trace_id = context.trace_id
            self._emit("access.credential.resolved", request_id=request.request_id, trace_id=trace_id, channel=request.channel, credential_id=credential_record.credential_id, outcome="resolved")
            self._emit("access.tenant.resolved", request_id=request.request_id, trace_id=trace_id, channel=request.channel, credential_id=credential_record.credential_id, outcome="resolved")
            policy = self.policy_registry.resolve(context.policy_profile)
            session_operation = str(raw_request.get("session_operation") or "")
            access_operation = str(raw_request.get("access_operation") or "")
            session_creation_data: dict[str, Any] = {}
            if session_operation == "session_creation" and self.session_creation_enricher is not None:
                session_creation_data = self.session_creation_enricher(request, context, credential_record)
            allow_empty_message = session_operation == "session_creation" or access_operation == "config_read" or bool(raw_request.get("allow_empty_message"))
            self._validate_limits(request, raw_request, policy.max_request_bytes, policy.max_message_characters, allow_empty_message=allow_empty_message)
            origin_result: OriginValidationResult | None = None
            if self.origin_validation_service is not None:
                origin_result = self.origin_validation_service.validate(
                    OriginValidationRequest(
                        credential_id=credential_record.credential_id,
                        credential_environment=credential_record.environment,
                        credential_type=credential_record.credential_type,
                        policy_profile=policy,
                        origin_header=request.origin,
                        referer_header=None,
                        request_method=str(raw_request.get("method") or "POST"),
                        channel=request.channel,
                        trusted_proxy_context=None,
                        request_id=request.request_id,
                        trace_id=trace_id,
                    )
                )
            if self.rate_limit_service is not None and not bool(raw_request.get("skip_rate_limit")):
                self.rate_limit_service.enforce(
                    RateLimitRequest(
                        request_id=request.request_id,
                        trace_id=trace_id,
                        environment=credential_record.environment,
                        channel=request.channel,
                        category=str(raw_request.get("rate_limit_category") or "internal_test"),
                        credential_id=credential_record.credential_id,
                        organisation_id=context.organisation_id,
                        workspace_id=context.workspace_id,
                        client_ip_identity=request.client_ip,
                        session_id=context.session_id,
                        policy_profile=policy,
                        request_cost=int(raw_request.get("rate_limit_cost") or 1),
                        received_at=request.received_at,
                    )
                )
            if access_operation == "config_read":
                if self.config_read_projector is None:
                    raise_public_error("temporarily_unavailable")
                projected = self.config_read_projector(request, context, credential_record, origin_result)
                payload = dict(projected.get("payload", {}))
                metadata: dict[str, str | int | float | bool | None] = {
                    "channel": request.channel,
                    "credential_id": credential_record.credential_id,
                }
                for key in ("etag", "configuration_version", "asset_omitted", "degraded_rate_limit"):
                    if key in projected:
                        value = projected[key]
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            metadata[key] = value
                response = PublicAccessResponse(
                    request_id=request.request_id,
                    trace_id=trace_id,
                    status="config_read",
                    payload=payload,
                    metadata=metadata,
                )
                return ValidatedAccessResult(request=request, context=context, response=response)
            session_payload: dict[str, Any] = {}
            canonical_origin = origin_result.canonical_origin.serialised if origin_result and origin_result.canonical_origin else None
            if session_operation:
                if self.public_session_service is None:
                    raise_public_error("temporarily_unavailable")
                inactivity_timeout_seconds = int(raw_request.get("inactivity_timeout_seconds") or min(policy.session_lifetime_seconds, 1800))
                if session_operation == "session_creation":
                    created = self.public_session_service.create_session(
                        CreatePublicSessionCommand(
                            organisation_id=context.organisation_id,
                            workspace_id=context.workspace_id,
                            credential_id=credential_record.credential_id,
                            channel=request.channel,
                            environment=credential_record.environment,
                            policy_profile=policy.policy_key,
                            origin_id=origin_result.matched_origin_id if origin_result else None,
                            canonical_origin=canonical_origin,
                            inactivity_timeout_seconds=inactivity_timeout_seconds,
                            absolute_lifetime_seconds=policy.session_lifetime_seconds,
                            max_messages=policy.max_messages_per_session,
                            metadata={"gateway_operation": "session_creation", **dict(session_creation_data.get("session_metadata", {}))},
                            request_id=request.request_id,
                            trace_id=trace_id,
                            received_at=request.received_at,
                        )
                    )
                    payload = created.to_dict()
                    payload.update(dict(session_creation_data.get("response_payload", {})))
                    response = PublicAccessResponse(
                        request_id=request.request_id,
                        trace_id=trace_id,
                        status="session_created",
                        payload=payload,
                        metadata={"channel": request.channel, "credential_id": credential_record.credential_id},
                    )
                    return ValidatedAccessResult(request=request, context=context, response=response)
                if session_operation != "session_validation":
                    raise_public_error("unsafe_request")
                if not request.public_session_token:
                    raise_public_error("invalid_session")
                validated_session = self.public_session_service.validate_session(
                    ValidatePublicSessionCommand(
                        public_session_token=request.public_session_token,
                        organisation_id=context.organisation_id,
                        workspace_id=context.workspace_id,
                        credential_id=credential_record.credential_id,
                        channel=request.channel,
                        environment=credential_record.environment,
                        policy_profile=policy.policy_key,
                        canonical_origin=canonical_origin,
                        received_at=request.received_at,
                        request_id=request.request_id,
                        trace_id=trace_id,
                    ),
                    max_messages=policy.max_messages_per_session,
                    inactivity_timeout_seconds=inactivity_timeout_seconds,
                )
                context = replace(context, session_id=validated_session.internal_session_id, rate_limit_identity=validated_session.rate_limit_identity)
                session_payload = {
                    "remaining_messages": validated_session.remaining_messages,
                    "expires_at": validated_session.expires_at.isoformat(),
                    "absolute_expires_at": validated_session.absolute_expires_at.isoformat(),
                }
                if bool(raw_request.get("consume_message_slot")):
                    consumed = self.public_session_service.consume_message_slot(
                        validated_session,
                        max_messages=policy.max_messages_per_session,
                        inactivity_timeout_seconds=inactivity_timeout_seconds,
                    )
                    session_payload["remaining_messages"] = consumed.remaining_messages
            self._emit("access.request.validated", request_id=request.request_id, trace_id=trace_id, channel=request.channel, credential_id=credential_record.credential_id, outcome="validated")
            payload = {"message": request.message}
            payload.update(session_payload)
            response = PublicAccessResponse(
                request_id=request.request_id,
                trace_id=trace_id,
                status="validated",
                payload=payload,
                metadata={"channel": request.channel, "credential_id": credential_record.credential_id},
            )
            return ValidatedAccessResult(request=request, context=context, response=response)
        except PublicAccessError as exc:
            self._emit("access.request.rejected", request_id=request_id, trace_id=trace_id, channel=channel or None, outcome="rejected", error_code=exc.code)
            response = PublicAccessResponse(
                request_id=request_id,
                trace_id=trace_id,
                status="rejected",
                safe_error=exc.detail,
            )
            return ValidatedAccessResult(
                request=request or self._fallback_request(request_id, channel),
                context=context or self._fallback_context(request_id, trace_id, channel),
                response=response,
            )
        except (ValueError, TypeError):
            detail = error_detail("unsafe_request")
            self._emit("access.request.rejected", request_id=request_id, trace_id=trace_id, channel=channel or None, outcome="rejected", error_code=detail.code)
            response = PublicAccessResponse(request_id=request_id, trace_id=trace_id, status="rejected", safe_error=detail)
            return ValidatedAccessResult(
                request=request or self._fallback_request(request_id, channel),
                context=context or self._fallback_context(request_id, trace_id, channel),
                response=response,
            )

    def _validate_limits(self, request: PublicAccessRequest, raw_request: dict[str, Any], max_request_bytes: int, max_message_characters: int, *, allow_empty_message: bool = False) -> None:
        if len(str(raw_request).encode("utf-8")) > max_request_bytes:
            raise_public_error("request_too_large")
        if not allow_empty_message and not request.message.strip():
            raise_public_error("unsafe_request")
        if len(request.message) > max_message_characters:
            raise_public_error("message_too_large")

    def _emit(self, event_type: str, *, request_id: str, trace_id: str, channel: str | None = None, credential_id: str | None = None, outcome: str | None = None, error_code: str | None = None) -> None:
        self.event_sink.emit(
            AccessEvent(
                event_type=event_type,
                request_id=request_id,
                trace_id=trace_id,
                channel=channel,
                credential_id=credential_id,
                outcome=outcome,
                error_code=error_code,
            )
        )

    def _fallback_request(self, request_id: str, channel: str) -> PublicAccessRequest:
        from app.access.contracts import PublicCredentialReference

        return PublicAccessRequest(
            request_id=request_id,
            channel=channel or "unsupported",
            public_credential=PublicCredentialReference(
                credential_type="widget_public_key",
                public_identifier="invalid",
            ),
            message="rejected",
        )

    def _fallback_context(self, request_id: str, trace_id: str, channel: str) -> NormalisedAccessContext:
        from app.access.contracts import CostLimits, utc_now

        return NormalisedAccessContext(
            request_id=request_id,
            trace_id=trace_id,
            organisation_id="unresolved",
            workspace_id="unresolved",
            channel=channel or "unsupported",
            credential_id="unresolved",
            policy_profile="unresolved",
            cost_limits=CostLimits(max_output_tokens=0, request_timeout_seconds=0),
            received_at=utc_now(),
        )
