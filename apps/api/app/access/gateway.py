from dataclasses import dataclass
from typing import Any

from app.access.channels.base import PublicChannelAdapter
from app.access.contracts import NormalisedAccessContext, PublicAccessRequest, PublicAccessResponse
from app.access.errors import PublicAccessError, error_detail, raise_public_error
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.policies.registry import AccessPolicyRegistry
from app.access.tenant_resolution.service import PublicTenantResolutionService


class DuplicateChannelError(ValueError):
    pass


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
    ) -> None:
        self.channel_registry = channel_registry
        self.tenant_resolution_service = tenant_resolution_service
        self.policy_registry = policy_registry
        self.event_sink = event_sink

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
            self._validate_limits(request, raw_request, policy.max_request_bytes, policy.max_message_characters)
            self._emit("access.request.validated", request_id=request.request_id, trace_id=trace_id, channel=request.channel, credential_id=credential_record.credential_id, outcome="validated")
            response = PublicAccessResponse(
                request_id=request.request_id,
                trace_id=trace_id,
                status="validated",
                payload={"message": request.message},
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

    def _validate_limits(self, request: PublicAccessRequest, raw_request: dict[str, Any], max_request_bytes: int, max_message_characters: int) -> None:
        if len(str(raw_request).encode("utf-8")) > max_request_bytes:
            raise_public_error("request_too_large")
        if not request.message.strip():
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
