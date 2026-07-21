from dataclasses import dataclass
from datetime import datetime, timezone

from app.access.errors import raise_public_error
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.rate_limit.contracts import RateLimitDecision, RateLimitRequest, RateLimitRule
from app.access.rate_limit.errors import RateLimitInvalidPolicy, RateLimitStoreError, RateLimitStoreTimeout
from app.access.rate_limit.identities import identity_for_rule, redis_rate_key
from app.access.rate_limit.local_fallback import LocalFallbackLimiter
from app.access.rate_limit.policies import rules_for_category
from app.access.rate_limit.redis_store import RateLimitStore
from app.access.rate_limit.token_bucket import reset_at_from_now


@dataclass(frozen=True)
class EmergencyControls:
    deny_all: bool = False
    disabled_channels: tuple[str, ...] = ()
    suspended_workspaces: tuple[str, ...] = ()
    reduced_limit_mode: bool = False


class RateLimitService:
    def __init__(
        self,
        *,
        store: RateLimitStore,
        identity_secret: str,
        redis_prefix: str = "rate",
        event_sink: InMemoryAccessEventSink | None = None,
        local_fallback: LocalFallbackLimiter | None = None,
        emergency_controls: EmergencyControls | None = None,
    ) -> None:
        self.store = store
        self.identity_secret = identity_secret
        self.redis_prefix = redis_prefix
        self.event_sink = event_sink
        self.local_fallback = local_fallback or LocalFallbackLimiter(enabled=False)
        self.emergency_controls = emergency_controls or EmergencyControls()

    def check(self, request: RateLimitRequest) -> RateLimitDecision:
        emergency = self._emergency_decision(request)
        if emergency is not None:
            self._emit("rate_limit.emergency_mode", request, emergency)
            return emergency
        rules = rules_for_category(request.policy_profile, request.category)
        if not rules:
            decision = RateLimitDecision(allowed=True, reason_code="not_configured", safe_metadata=self._metadata(request))
            self._emit("rate_limit.allowed", request, decision)
            return decision
        now = request.received_at if request.received_at.tzinfo else request.received_at.replace(tzinfo=timezone.utc)
        for rule in rules:
            identity = identity_for_rule(rule, request=request, secret=self.identity_secret)
            if identity is None:
                decision = self._deny(request, rule, reason_code="rate_limited", retry_after_seconds=rule.retry_after_cap_seconds)
                self._emit("rate_limit.denied", request, decision)
                return decision
            key = redis_rate_key(prefix=self.redis_prefix, environment=request.environment, dimension=rule.dimension, identity=identity, category=rule.category)
            try:
                state = self.store.consume(key=key, rule=rule, request_cost=max(request.request_cost, rule.request_cost), now=now)
            except RateLimitStoreTimeout:
                decision = self._handle_store_failure(request, rule, now, timeout=True)
                return decision
            except RateLimitStoreError:
                decision = self._handle_store_failure(request, rule, now, timeout=False)
                return decision
            if not state.allowed:
                decision = RateLimitDecision(
                    allowed=False,
                    reason_code="rate_limited",
                    limiting_dimension=rule.dimension,
                    rule_key=rule.rule_key,
                    limit=rule.capacity,
                    remaining=state.remaining,
                    retry_after_seconds=state.retry_after_seconds,
                    reset_at=reset_at_from_now(now, state.reset_after_seconds),
                    degraded=False,
                    safe_metadata=self._metadata(request, rule),
                )
                self._emit("rate_limit.denied", request, decision)
                return decision
        decision = RateLimitDecision(allowed=True, reason_code="allowed", degraded=False, safe_metadata=self._metadata(request))
        self._emit("rate_limit.allowed", request, decision)
        return decision

    def enforce(self, request: RateLimitRequest) -> RateLimitDecision:
        decision = self.check(request)
        if decision.allowed:
            return decision
        if decision.reason_code == "temporarily_unavailable":
            raise_public_error("temporarily_unavailable", retry_after_seconds=decision.retry_after_seconds)
        raise_public_error("rate_limited", retry_after_seconds=decision.retry_after_seconds)

    def _handle_store_failure(self, request: RateLimitRequest, rule: RateLimitRule, now: datetime, *, timeout: bool) -> RateLimitDecision:
        event_type = "rate_limit.redis_timeout" if timeout else "rate_limit.redis_unavailable"
        if rule.fail_mode in {"constrained_fail_open", "local_degraded"}:
            local = self.local_fallback.consume(key=f"local:{rule.rule_key}:{request.credential_id}:{request.client_ip_identity or 'unknown'}", rule=rule, request_cost=max(request.request_cost, rule.request_cost), now=now)
            if local is not None:
                decision = RateLimitDecision(
                    allowed=local.allowed,
                    reason_code="allowed_degraded" if local.allowed else "rate_limited",
                    limiting_dimension=None if local.allowed else rule.dimension,
                    rule_key=rule.rule_key,
                    limit=rule.capacity,
                    remaining=local.remaining,
                    retry_after_seconds=None if local.allowed else local.retry_after_seconds,
                    reset_at=reset_at_from_now(now, local.reset_after_seconds),
                    degraded=True,
                    safe_metadata=self._metadata(request, rule),
                )
                self._emit("rate_limit.degraded_local_fallback", request, decision)
                return decision
        decision = self._deny(request, rule, reason_code="temporarily_unavailable")
        self._emit(event_type, request, decision)
        return decision

    def _emergency_decision(self, request: RateLimitRequest) -> RateLimitDecision | None:
        controls = self.emergency_controls
        if controls.deny_all or request.channel in controls.disabled_channels or request.workspace_id in controls.suspended_workspaces:
            return RateLimitDecision(allowed=False, reason_code="temporarily_unavailable", degraded=False, safe_metadata=self._metadata(request))
        return None

    def _deny(self, request: RateLimitRequest, rule: RateLimitRule, *, reason_code: str, retry_after_seconds: int | None = None) -> RateLimitDecision:
        return RateLimitDecision(
            allowed=False,
            reason_code=reason_code,
            limiting_dimension=rule.dimension,
            rule_key=rule.rule_key,
            limit=rule.capacity,
            remaining=0,
            retry_after_seconds=retry_after_seconds,
            degraded=False,
            safe_metadata=self._metadata(request, rule),
        )

    def _metadata(self, request: RateLimitRequest, rule: RateLimitRule | None = None) -> dict[str, str | int | bool | None]:
        return {
            "channel": request.channel,
            "category": request.category,
            "credential_id": request.credential_id,
            "workspace_id": request.workspace_id,
            "limiting_dimension": rule.dimension if rule else None,
            "rule_key": rule.rule_key if rule else None,
        }

    def _emit(self, event_type: str, request: RateLimitRequest, decision: RateLimitDecision) -> None:
        if self.event_sink is None:
            return
        self.event_sink.emit(
            AccessEvent(
                event_type=event_type,
                request_id=request.request_id,
                trace_id=request.trace_id,
                channel=request.channel,
                credential_id=request.credential_id,
                outcome="allowed" if decision.allowed else "denied",
                error_code=None if decision.allowed else decision.reason_code,
            )
        )
