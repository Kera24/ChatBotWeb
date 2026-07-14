from collections.abc import Callable

from app.access.errors import raise_public_error
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.origin_validation.contracts import (
    MATCH_NONE,
    SOURCE_MISSING,
    SOURCE_ORIGIN_HEADER,
    SOURCE_POLICY_EXCEPTION,
    AllowedOriginRecord,
    OriginValidationRequest,
    OriginValidationResult,
)
from app.access.origin_validation.errors import OriginNormalisationError
from app.access.origin_validation.matcher import match_origin
from app.access.origin_validation.normalisation import normalise_origin_header

OriginLookup = Callable[[str, str], list[AllowedOriginRecord]]


class OriginValidationService:
    def __init__(self, *, origin_lookup: OriginLookup, event_sink: InMemoryAccessEventSink | None = None) -> None:
        self.origin_lookup = origin_lookup
        self.event_sink = event_sink

    def validate(self, request: OriginValidationRequest) -> OriginValidationResult:
        policy_origin_required = bool(getattr(request.policy_profile, "origin_required", False))
        if request.credential_type == "partner_api_key" and not policy_origin_required:
            result = OriginValidationResult(
                allowed=True,
                canonical_origin=None,
                matched_origin_id=None,
                match_type=MATCH_NONE,
                decision_source=SOURCE_POLICY_EXCEPTION,
                reason_code="not_applicable",
                environment=request.credential_environment,
                safe_metadata={"channel": request.channel, "credential_id": request.credential_id},
            )
            self._emit("origin.validation.development_exception", request, result)
            return result
        if not request.origin_header:
            if policy_origin_required:
                result = self._deny(request, reason_code="origin_required", decision_source=SOURCE_MISSING)
                self._emit("origin.validation.missing", request, result)
                raise_public_error("origin_required")
            result = OriginValidationResult(
                allowed=True,
                canonical_origin=None,
                matched_origin_id=None,
                match_type=MATCH_NONE,
                decision_source=SOURCE_POLICY_EXCEPTION,
                reason_code="not_required",
                environment=request.credential_environment,
                safe_metadata={"channel": request.channel, "credential_id": request.credential_id},
            )
            self._emit("origin.validation.development_exception", request, result)
            return result

        try:
            canonical = normalise_origin_header(request.origin_header)
        except OriginNormalisationError as exc:
            result = self._deny(request, reason_code=exc.reason_code, decision_source=SOURCE_ORIGIN_HEADER)
            self._emit("origin.validation.malformed", request, result)
            raise_public_error(exc.reason_code)

        environment_error = self._environment_error(canonical, request.credential_environment)
        if environment_error is not None:
            result = OriginValidationResult(
                allowed=False,
                canonical_origin=canonical,
                matched_origin_id=None,
                match_type=MATCH_NONE,
                decision_source=SOURCE_ORIGIN_HEADER,
                reason_code=environment_error,
                environment=request.credential_environment,
                safe_metadata=self._safe_metadata(request, canonical.hostname),
            )
            self._emit("origin.validation.denied", request, result)
            raise_public_error(environment_error)

        try:
            origins = [origin for origin in self.origin_lookup(request.credential_id, request.credential_environment) if origin.credential_id == request.credential_id]
        except Exception:
            result = self._deny(request, reason_code="temporarily_unavailable", decision_source=SOURCE_ORIGIN_HEADER)
            self._emit("origin.validation.denied", request, result)
            raise_public_error("temporarily_unavailable")

        match_type, matched = match_origin(canonical, origins, environment=request.credential_environment)
        if matched is None:
            result = OriginValidationResult(
                allowed=False,
                canonical_origin=canonical,
                matched_origin_id=None,
                match_type=MATCH_NONE,
                decision_source=SOURCE_ORIGIN_HEADER,
                reason_code="origin_not_allowed",
                environment=request.credential_environment,
                safe_metadata=self._safe_metadata(request, canonical.hostname),
            )
            self._emit("origin.validation.denied", request, result)
            raise_public_error("origin_not_allowed")

        result = OriginValidationResult(
            allowed=True,
            canonical_origin=canonical,
            matched_origin_id=matched.origin_id,
            match_type=match_type,
            decision_source=SOURCE_ORIGIN_HEADER,
            reason_code="allowed",
            environment=request.credential_environment,
            safe_metadata=self._safe_metadata(request, canonical.hostname, matched.origin_id),
        )
        event_type = "origin.validation.wildcard_matched" if match_type == "wildcard" else "origin.validation.allowed"
        self._emit(event_type, request, result)
        return result

    def _environment_error(self, canonical, environment: str) -> str | None:
        if environment == "production":
            if canonical.scheme != "https":
                return "insecure_origin"
            if canonical.is_loopback:
                return "origin_not_allowed"
        if environment == "staging" and canonical.is_loopback:
            return "origin_not_allowed"
        if environment not in {"development", "staging", "production"}:
            return "origin_not_allowed"
        return None

    def _deny(self, request: OriginValidationRequest, *, reason_code: str, decision_source: str) -> OriginValidationResult:
        return OriginValidationResult(
            allowed=False,
            canonical_origin=None,
            matched_origin_id=None,
            match_type=MATCH_NONE,
            decision_source=decision_source,
            reason_code=reason_code,
            environment=request.credential_environment,
            safe_metadata={"channel": request.channel, "credential_id": request.credential_id},
        )

    def _safe_metadata(self, request: OriginValidationRequest, hostname: str | None, matched_origin_id: str | None = None) -> dict[str, str | int | bool | None]:
        return {
            "channel": request.channel,
            "credential_id": request.credential_id,
            "hostname": hostname,
            "matched_origin_id": matched_origin_id,
        }

    def _emit(self, event_type: str, request: OriginValidationRequest, result: OriginValidationResult) -> None:
        if self.event_sink is None:
            return
        self.event_sink.emit(
            AccessEvent(
                event_type=event_type,
                request_id=request.request_id,
                trace_id=request.trace_id,
                channel=request.channel,
                credential_id=request.credential_id,
                outcome="allowed" if result.allowed else "denied",
                error_code=None if result.allowed else result.reason_code,
            )
        )




